// Author: Zulqarnain Ahmad (Freelancer: https://www.freelancer.com/u/zulqarnaina43)
// In collaboration with team leader: Afaq Ahmad (Freelancer: https://www.freelancer.com/u/AFAQCEO , GitHub: https://github.com/H-tech-AFAQ-CEO)

// Twice-weekly Walmart scraper on Azure Container Apps Jobs. NOT deployed/tested from the build sandbox
// (no Azure access there) - run `az deployment group what-if` first.
param location string = resourceGroup().location
param image string                       // e.g. myacr.azurecr.io/walmart-scraper:1.0.0
param acrServer string
param locationIds array = [ 'store_1' ]  // one job per configured location id
@description('Cron in UTC. Default: Mon & Thu 08:00 UTC = twice weekly')
param cron string = '0 8 * * 1,4'
@secure()
param proxyUrl string = ''               // optional; stored as a Container Apps secret, never in source

var suffix = uniqueString(resourceGroup().id)

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'ws-logs-${suffix}'
  location: location
  properties: { sku: { name: 'PerGB2018' }, retentionInDays: 30 }
}

resource sa 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: 'wsdata${suffix}'
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: { allowSharedKeyAccess: true, minimumTlsVersion: 'TLS1_2', allowBlobPublicAccess: false }
}
resource blobSvc 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = { parent: sa, name: 'default' }
resource cont 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = { parent: blobSvc, name: 'walmart' }
resource fileSvc 'Microsoft.Storage/storageAccounts/fileServices@2023-05-01' = { parent: sa, name: 'default' }
resource share 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-05-01' = { parent: fileSvc, name: 'state' }

resource id 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = { name: 'ws-id-${suffix}', location: location }

var blobContributor = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
var acrPull = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
resource ra 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(sa.id, id.id, blobContributor)
  scope: sa
  properties: { roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', blobContributor), principalId: id.properties.principalId, principalType: 'ServicePrincipal' }
}

resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'ws-env-${suffix}'
  location: location
  properties: {
    appLogsConfiguration: { destination: 'log-analytics', logAnalyticsConfiguration: { customerId: logs.properties.customerId, sharedKey: logs.listKeys().primarySharedKey } }
  }
}
resource envStorage 'Microsoft.App/managedEnvironments/storages@2024-03-01' = {
  parent: env
  name: 'state'
  properties: { azureFile: { accountName: sa.name, accountKey: sa.listKeys().keys[0].value, shareName: 'state', accessMode: 'ReadWrite' } }
}

resource jobs 'Microsoft.App/jobs@2024-03-01' = [for loc in locationIds: {
  name: 'ws-${toLower(replace(loc, '_', '-'))}'
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${id.id}': {} } }
  properties: {
    environmentId: env.id
    configuration: {
      triggerType: 'Schedule'
      scheduleTriggerConfig: { cronExpression: cron, parallelism: 1, replicaCompletionCount: 1 }
      replicaTimeout: 43200          // 12h; checkpoints make interrupted runs resumable
      replicaRetryLimit: 3           // retry resumes from checkpoint
      registries: [ { server: acrServer, identity: id.id } ]
      secrets: empty(proxyUrl) ? [] : [ { name: 'proxy-url', value: proxyUrl } ]
    }
    template: {
      containers: [ {
        name: 'scraper'
        image: image
        args: [ 'run', '--location', loc ]
        resources: { cpu: json('2.0'), memory: '4Gi' }
        env: concat([
          { name: 'WS_AZURE_ACCOUNT_URL', value: sa.properties.primaryEndpoints.blob }
          { name: 'AZURE_CLIENT_ID', value: id.properties.clientId }
        ], empty(proxyUrl) ? [] : [ { name: 'WS_PROXY_URL', secretRef: 'proxy-url' } ])
        volumeMounts: [ { volumeName: 'state', mountPath: '/mnt/state' } ]
      } ]
      volumes: [ { name: 'state', storageType: 'AzureFile', storageName: envStorage.name } ]
    }
  }
}]
