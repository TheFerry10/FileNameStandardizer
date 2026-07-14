data "azurerm_client_config" "current" {}

resource "random_string" "storage_suffix" {
  length  = 6
  upper   = false
  special = false
}

locals {
  normalized_project_name = lower(replace(var.project_name, "-", ""))
  generated_storage_name  = substr("${local.normalized_project_name}${var.environment}${random_string.storage_suffix.result}", 0, 24)
  storage_account_name    = var.storage_account_name != "" ? var.storage_account_name : local.generated_storage_name

  tags = {
    project     = var.project_name
    environment = var.environment
    managed_by  = "terraform"
  }
}

resource "azurerm_resource_group" "this" {
  name     = var.resource_group_name
  location = var.location
  tags     = local.tags
}

resource "azurerm_storage_account" "this" {
  name                     = local.storage_account_name
  resource_group_name      = azurerm_resource_group.this.name
  location                 = azurerm_resource_group.this.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  account_kind             = "StorageV2"
  min_tls_version          = "TLS1_2"
  tags                     = local.tags
}

resource "azurerm_storage_container" "required" {
  for_each              = var.storage_containers
  name                  = each.value
  storage_account_name  = azurerm_storage_account.this.name
  container_access_type = "private"
}

resource "azurerm_service_plan" "this" {
  name                = "${var.function_app_name}-plan"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  os_type             = "Linux"
  sku_name            = "Y1"
  tags                = local.tags
}

resource "azurerm_linux_function_app" "this" {
  name                = var.function_app_name
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location

  service_plan_id            = azurerm_service_plan.this.id
  storage_account_name       = azurerm_storage_account.this.name
  storage_account_access_key = azurerm_storage_account.this.primary_access_key

  https_only = true

  identity {
    type = "SystemAssigned"
  }

  site_config {
    application_stack {
      python_version = var.python_version
    }
  }

  app_settings = {
    FUNCTIONS_EXTENSION_VERSION         = "~4"
    FUNCTIONS_WORKER_RUNTIME            = "python"
    STORAGE_CONNECTION__blobServiceUri  = azurerm_storage_account.this.primary_blob_endpoint
    STORAGE_CONNECTION__queueServiceUri = azurerm_storage_account.this.primary_queue_endpoint
    AzureWebJobsStorage                 = azurerm_storage_account.this.primary_connection_string
  }

  tags = local.tags
}

resource "azurerm_role_assignment" "function_storage" {
  for_each = toset([
    "Storage Blob Data Contributor",
    "Storage Blob Delegator",
    "Storage Queue Data Contributor",
  ])

  scope                = azurerm_storage_account.this.id
  role_definition_name = each.value
  principal_id         = azurerm_linux_function_app.this.identity[0].principal_id
}

resource "azuread_application" "github" {
  display_name = var.github_app_registration_name
}

resource "azuread_service_principal" "github" {
  client_id = azuread_application.github.client_id
}

resource "azuread_application_federated_identity_credential" "github" {
  application_id = azuread_application.github.id
  display_name   = "github-actions-${var.environment}"
  audiences      = ["api://AzureADTokenExchange"]
  issuer         = "https://token.actions.githubusercontent.com"
  subject        = "repo:${var.github_repository_owner}/${var.github_repository_name}:ref:refs/heads/${var.github_branch}"
}

resource "azurerm_role_assignment" "github_deployer" {
  scope                = azurerm_resource_group.this.id
  role_definition_name = "Contributor"
  principal_id         = azuread_service_principal.github.object_id
}
