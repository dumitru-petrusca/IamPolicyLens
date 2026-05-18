from typing import List, Optional


# Static mapping of Python AI agent instantiations to their implicit required IAM permissions
_PYTHON_AGENT_TO_PERMISSIONS = {
    "google.adk.agents.llm_agent.LlmAgent": [
        "aiplatform.endpoints.predict",
        "aiplatform.reasoningEngines.predict",
        "aiplatform.reasoningEngines.list",
        "aiplatform.reasoningEngines.get"
    ],
    "google.adk.agents.llm_agent.Agent": [
        "aiplatform.endpoints.predict",
        "aiplatform.reasoningEngines.predict",
        "aiplatform.reasoningEngines.list",
        "aiplatform.reasoningEngines.get"
    ],
    "google.adk.agents.base_agent.BaseAgent": [
        "aiplatform.endpoints.predict",
        "aiplatform.reasoningEngines.predict",
        "aiplatform.reasoningEngines.list",
        "aiplatform.reasoningEngines.get"
    ],
    "google.adk.agents.loop_agent.LoopAgent": [
        "aiplatform.endpoints.predict",
        "aiplatform.reasoningEngines.predict",
        "aiplatform.reasoningEngines.list",
        "aiplatform.reasoningEngines.get"
    ],
    "google.adk.agents.parallel_agent.ParallelAgent": [
        "aiplatform.endpoints.predict",
        "aiplatform.reasoningEngines.predict",
        "aiplatform.reasoningEngines.list",
        "aiplatform.reasoningEngines.get"
    ],
    "google.adk.agents.sequential_agent.SequentialAgent": [
        "aiplatform.endpoints.predict",
        "aiplatform.reasoningEngines.predict",
        "aiplatform.reasoningEngines.list",
        "aiplatform.reasoningEngines.get"
    ],
    "google.adk.agents.langgraph_agent.LanggraphAgent": [
        "aiplatform.endpoints.predict",
        "aiplatform.reasoningEngines.predict",
        "aiplatform.reasoningEngines.list",
        "aiplatform.reasoningEngines.get"
    ],
    "google.adk.agents.remote_a2a_agent.RemoteA2aAgent": [
        "aiplatform.endpoints.predict",
        "aiplatform.reasoningEngines.predict",
        "aiplatform.reasoningEngines.list",
        "aiplatform.reasoningEngines.get"
    ],
    "google.adk.agents.Agent": [
        "aiplatform.endpoints.predict",
        "aiplatform.reasoningEngines.predict",
        "aiplatform.reasoningEngines.list",
        "aiplatform.reasoningEngines.get"
    ],
    "google.adk.agents.LlmAgent": [
        "aiplatform.endpoints.predict",
        "aiplatform.reasoningEngines.predict",
        "aiplatform.reasoningEngines.list",
        "aiplatform.reasoningEngines.get"
    ],
    "google.adk.agents.BaseAgent": [
        "aiplatform.endpoints.predict",
        "aiplatform.reasoningEngines.predict",
        "aiplatform.reasoningEngines.list",
        "aiplatform.reasoningEngines.get"
    ],
    "google.adk.agents.LoopAgent": [
        "aiplatform.endpoints.predict",
        "aiplatform.reasoningEngines.predict",
        "aiplatform.reasoningEngines.list",
        "aiplatform.reasoningEngines.get"
    ],
    "google.adk.agents.ParallelAgent": [
        "aiplatform.endpoints.predict",
        "aiplatform.reasoningEngines.predict",
        "aiplatform.reasoningEngines.list",
        "aiplatform.reasoningEngines.get"
    ],
    "google.adk.agents.SequentialAgent": [
        "aiplatform.endpoints.predict",
        "aiplatform.reasoningEngines.predict",
        "aiplatform.reasoningEngines.list",
        "aiplatform.reasoningEngines.get"
    ],
    "google.adk.agents.LanggraphAgent": [
        "aiplatform.endpoints.predict",
        "aiplatform.reasoningEngines.predict",
        "aiplatform.reasoningEngines.list",
        "aiplatform.reasoningEngines.get"
    ],
    "google.adk.agents.RemoteA2aAgent": [
        "aiplatform.endpoints.predict",
        "aiplatform.reasoningEngines.predict",
        "aiplatform.reasoningEngines.list",
        "aiplatform.reasoningEngines.get"
    ],
}

# Static mapping of Go AI agent instantiations to their implicit required IAM permissions
_GO_AGENT_TO_PERMISSIONS = {
    "google.golang.org/adk/agent/llmagent.New": [
        "aiplatform.endpoints.predict",
        "aiplatform.reasoningEngines.predict",
        "aiplatform.reasoningEngines.list",
        "aiplatform.reasoningEngines.get"
    ],
    "google.golang.org/adk/agent/loopagent.New": [
        "aiplatform.endpoints.predict",
        "aiplatform.reasoningEngines.predict",
        "aiplatform.reasoningEngines.list",
        "aiplatform.reasoningEngines.get"
    ],
    "google.golang.org/adk/agent/parallelagent.New": [
        "aiplatform.endpoints.predict",
        "aiplatform.reasoningEngines.predict",
        "aiplatform.reasoningEngines.list",
        "aiplatform.reasoningEngines.get"
    ],
    "google.golang.org/adk/agent/sequentialagent.New": [
        "aiplatform.endpoints.predict",
        "aiplatform.reasoningEngines.predict",
        "aiplatform.reasoningEngines.list",
        "aiplatform.reasoningEngines.get"
    ],
    "google.golang.org/adk/agent/baseagent.New": [
        "aiplatform.endpoints.predict",
        "aiplatform.reasoningEngines.predict",
        "aiplatform.reasoningEngines.list",
        "aiplatform.reasoningEngines.get"
    ],
    "google.golang.org/adk/agent.NewSingleLoader": [
        "aiplatform.endpoints.predict",
        "aiplatform.reasoningEngines.predict",
        "aiplatform.reasoningEngines.list",
        "aiplatform.reasoningEngines.get"
    ],
    "google.golang.org/adk/agent.NewMultiLoader": [
        "aiplatform.endpoints.predict",
        "aiplatform.reasoningEngines.predict",
        "aiplatform.reasoningEngines.list",
        "aiplatform.reasoningEngines.get"
    ],
}

# Static mapping of TypeScript/Node.js AI agent instantiations to their implicit required IAM permissions
_TS_AGENT_TO_PERMISSIONS = {
    "@google/adk.LlmAgent": [
        "aiplatform.endpoints.predict",
        "aiplatform.reasoningEngines.predict",
        "aiplatform.reasoningEngines.list",
        "aiplatform.reasoningEngines.get"
    ],
    "@google/adk.LoopAgent": [
        "aiplatform.endpoints.predict",
        "aiplatform.reasoningEngines.predict",
        "aiplatform.reasoningEngines.list",
        "aiplatform.reasoningEngines.get"
    ],
    "@google/adk.ParallelAgent": [
        "aiplatform.endpoints.predict",
        "aiplatform.reasoningEngines.predict",
        "aiplatform.reasoningEngines.list",
        "aiplatform.reasoningEngines.get"
    ],
    "@google/adk.SequentialAgent": [
        "aiplatform.endpoints.predict",
        "aiplatform.reasoningEngines.predict",
        "aiplatform.reasoningEngines.list",
        "aiplatform.reasoningEngines.get"
    ],
    "@google/adk.BaseAgent": [
        "aiplatform.endpoints.predict",
        "aiplatform.reasoningEngines.predict",
        "aiplatform.reasoningEngines.list",
        "aiplatform.reasoningEngines.get"
    ],
    "@google/adk.Agent": [
        "aiplatform.endpoints.predict",
        "aiplatform.reasoningEngines.predict",
        "aiplatform.reasoningEngines.list",
        "aiplatform.reasoningEngines.get"
    ],
}


# Static mapping of Python resolved GAPIC methods to required IAM permissions
# This mapping is a hack and will be replaced with actual pre-computed mappings.
_PYTHON_METHOD_TO_PERMISSIONS = {
    # Compute Engine
    "google.cloud.compute_v1.InstancesClient.aggregated_list": ["compute.instances.list"],
    "google.cloud.compute_v1.InstancesClient.list": ["compute.instances.list"],
    
    # GKE (Kubernetes Engine)
    "google.cloud.container_v1.ClusterManagerClient.list_clusters": ["container.clusters.list"],
    "google.cloud.container_v1.ClusterManagerClient.get_cluster": ["container.clusters.get"],
    
    # Cloud Asset Inventory
    "google.cloud.asset_v1.AssetServiceClient.list_assets": ["cloudasset.assets.searchAllResources"],
    
    # BigQuery
    "google.cloud.bigquery.Client.query": ["bigquery.jobs.create"],
    "google.cloud.bigquery.Client.list_tables": [
        "bigquery.datasets.get",
        "bigquery.tables.list"
    ],
    "google.cloud.bigquery.Client.get_dataset": ["bigquery.datasets.get"],
    "google.cloud.bigquery.Client.create_dataset": ["bigquery.datasets.create"],
    "google.cloud.bigquery.Client.load_table_from_file": [
        "bigquery.tables.create",
        "bigquery.tables.updateData"
    ],
    "google.cloud.bigquery.dataset.Dataset": ["bigquery.datasets.get"],
    "google.cloud.bigquery.dataset.DatasetReference": ["bigquery.datasets.get"],
    "google.cloud.bigquery.table.TableReference": ["bigquery.tables.get"],
    
    # Cloud Storage
    "google.cloud.storage.Client.lookup_bucket": ["storage.buckets.get"],
    "google.cloud.storage.Client.create_bucket": ["storage.buckets.create"],
    "google.cloud.storage.bucket.Bucket.patch": ["storage.buckets.update"],
    
    # Python Cloud Run
    "google.cloud.run_v2.ServicesClient.list_services": ["run.services.list"],
    "google.cloud.run_v2.ServicesClient.get_service": ["run.services.get"],
    
    # Vertex AI / reasoning engine
    "vertexai.agent_engines.create": [
        "aiplatform.reasoningEngines.create",
        "storage.buckets.create",
        "storage.buckets.get"
    ],
    "vertexai.agent_engines.get": ["aiplatform.reasoningEngines.get"],
    "vertexai.agent_engines.delete": ["aiplatform.reasoningEngines.delete"],
}

# Static mapping of Go resolved GAPIC methods to required IAM permissions
# This mapping is a hack and will be replaced with actual pre-computed mappings.
_GO_METHOD_TO_PERMISSIONS = {
    # Go Compute Engine
    "cloud.google.com/go/compute/apiv1.InstancesClient.AggregatedList": ["compute.instances.list"],
    "cloud.google.com/go/compute/apiv1.InstancesClient.List": ["compute.instances.list"],

    # Go GKE (Kubernetes Engine)
    "cloud.google.com/go/container/apiv1.ClusterManagerClient.ListClusters": ["container.clusters.list"],
    "cloud.google.com/go/container/apiv1.ClusterManagerClient.GetCluster": ["container.clusters.get"],

    # Go Cloud Asset Inventory
    "cloud.google.com/go/asset/apiv1.Client.ListAssets": ["cloudasset.assets.searchAllResources"],

    # Go BigQuery
    "cloud.google.com/go/bigquery.Client.Query": ["bigquery.jobs.create"],
    "cloud.google.com/go/bigquery.Dataset.Tables": ["bigquery.tables.list"],
    "cloud.google.com/go/bigquery.Client.DatasetInProject": ["bigquery.datasets.get"],
    "cloud.google.com/go/bigquery.Client.Dataset": ["bigquery.datasets.get"],

    # Go Cloud Run
    "cloud.google.com/go/run/apiv2.ServicesClient.ListServices": ["run.services.list"],
    "cloud.google.com/go/run/apiv2.ServicesClient.GetService": ["run.services.get"],
}

# Static mapping of TypeScript / Node.js resolved GAPIC methods to required IAM permissions
# This mapping is a hack and will be replaced with actual pre-computed mappings.
_TS_METHOD_TO_PERMISSIONS = {
    # TypeScript / Node.js Compute Engine
    "@google-cloud/compute.InstancesClient.aggregatedListAsync": ["compute.instances.list"],
    "@google-cloud/compute.InstancesClient.listAsync": ["compute.instances.list"],

    # TypeScript / Node.js GKE (Kubernetes Engine)
    "@google-cloud/container.ClusterManagerClient.listClusters": ["container.clusters.list"],
    "@google-cloud/container.ClusterManagerClient.getCluster": ["container.clusters.get"],

    # TypeScript / Node.js Cloud Asset Inventory
    "@google-cloud/asset.AssetServiceClient.listAssets": ["cloudasset.assets.searchAllResources"],

    # TypeScript / Node.js BigQuery
    "@google-cloud/bigquery.BigQuery.query": ["bigquery.jobs.create"],
    "@google-cloud/bigquery.Dataset.getTables": ["bigquery.tables.list"],
    "@google-cloud/bigquery.BigQuery.dataset": ["bigquery.datasets.get"],

    # TypeScript / Node.js Cloud Run
    "@google-cloud/run.ServicesClient.listServices": ["run.services.list"],
    "@google-cloud/run.ServicesClient.getService": ["run.services.get"],
}

def gapic2permission(gapic_method: str) -> Optional[List[str]]:
    """Maps a fully qualified GAPIC method call string to its required IAM permissions list."""
    return (
        _PYTHON_METHOD_TO_PERMISSIONS.get(gapic_method)
        or _GO_METHOD_TO_PERMISSIONS.get(gapic_method)
        or _TS_METHOD_TO_PERMISSIONS.get(gapic_method)
        or _PYTHON_AGENT_TO_PERMISSIONS.get(gapic_method)
        or _GO_AGENT_TO_PERMISSIONS.get(gapic_method)
        or _TS_AGENT_TO_PERMISSIONS.get(gapic_method)
    )
