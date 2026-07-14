output "resource_group_name" {
  description = "Resource group name used for the deployment."
  value       = azurerm_resource_group.this.name
}

output "function_app_name" {
  description = "Function App name to be used by deployment workflows."
  value       = azurerm_linux_function_app.this.name
}

output "storage_account_name" {
  description = "Storage account backing Function runtime and data containers."
  value       = azurerm_storage_account.this.name
}

output "blob_service_uri" {
  description = "Blob service endpoint injected into app settings."
  value       = azurerm_storage_account.this.primary_blob_endpoint
}

output "queue_service_uri" {
  description = "Queue service endpoint injected into app settings."
  value       = azurerm_storage_account.this.primary_queue_endpoint
}

output "github_actions_client_id" {
  description = "Client ID for GitHub OIDC login (store as GitHub secret)."
  value       = azuread_application.github.client_id
}

output "github_actions_tenant_id" {
  description = "Tenant ID for GitHub OIDC login (store as GitHub secret)."
  value       = data.azurerm_client_config.current.tenant_id
}

output "github_actions_subscription_id" {
  description = "Subscription ID for GitHub OIDC login (store as GitHub secret)."
  value       = data.azurerm_client_config.current.subscription_id
}
