variable "project_name" {
  description = "Project prefix used for resource naming."
  type        = string
  default     = "filenamestandardizer"
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "dev"
}

variable "location" {
  description = "Azure region for resource deployment."
  type        = string
}

variable "resource_group_name" {
  description = "Name of the Azure resource group."
  type        = string
}

variable "storage_account_name" {
  description = "Optional explicit storage account name (3-24 lowercase letters/numbers)."
  type        = string
  default     = ""

  validation {
    condition     = var.storage_account_name == "" || can(regex("^[a-z0-9]{3,24}$", var.storage_account_name))
    error_message = "storage_account_name must be empty or 3-24 lowercase letters/numbers."
  }
}

variable "function_app_name" {
  description = "Name of the Azure Linux Function App."
  type        = string
}

variable "python_version" {
  description = "Python runtime version for the Function App."
  type        = string
  default     = "3.12"
}

variable "storage_containers" {
  description = "Blob containers required by the application flow."
  type        = set(string)
  default     = ["landing-zone", "processed", "failed"]
}

variable "github_repository_owner" {
  description = "GitHub organization or user that owns the repository."
  type        = string
}

variable "github_repository_name" {
  description = "GitHub repository name."
  type        = string
}

variable "github_branch" {
  description = "GitHub branch allowed to use OIDC federation."
  type        = string
  default     = "main"
}

variable "github_app_registration_name" {
  description = "Display name for the Entra app registration used by GitHub Actions."
  type        = string
  default     = "github-deploy-FileNameStandardizer"
}
