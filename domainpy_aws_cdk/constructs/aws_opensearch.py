import constructs
import aws_cdk as cdk
import aws_cdk.aws_iam as cdk_iam
import aws_cdk.aws_lambda as cdk_lambda
import aws_cdk.aws_opensearchservice as cdk_search
import aws_cdk.aws_secretsmanager as cdk_secrets
import aws_cdk.custom_resources as cdk_custom

from .aws_lambda import PackageAssetCode


class EnhacedDomain(constructs.Construct):
    def __init__(
        self,
        scope: constructs.Construct,
        id: str,
        *,
        username: str,
        data_node_instance_type: str = "t3.small.search",
        data_nodes: int = 1,
    ) -> None:
        super().__init__(scope, id)

        self.username = username

        self.secret = cdk_secrets.Secret(
            self,
            "secret",
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        self.domain = cdk_search.Domain(
            self,
            "domain",
            version=cdk_search.EngineVersion.OPENSEARCH_1_0,
            capacity=cdk_search.CapacityConfig(
                data_node_instance_type=data_node_instance_type,
                data_nodes=data_nodes,
            ),
            access_policies=[
                cdk_iam.PolicyStatement(
                    effect=cdk_iam.Effect.ALLOW,
                    actions=["es:*"],
                    resources=["*"],
                    principals=[cdk_iam.AnyPrincipal()],
                )
            ],
            fine_grained_access_control=cdk_search.AdvancedSecurityOptions(
                master_user_name=self.username,
                master_user_password=self.secret.secret_value,
            ),
            encryption_at_rest=cdk_search.EncryptionAtRestOptions(
                enabled=True
            ),
            node_to_node_encryption=True,
            enable_version_upgrade=True,
            enforce_https=True,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        on_event_handler = cdk_lambda.Function(
            self,
            "on_event",
            code=cdk_lambda.Code.from_inline(ON_EVENT_CODE),
            handler="index.handler",
            runtime=cdk_lambda.Runtime.PYTHON_3_8,
            description="[CustomOpenSearchServiceProvider:on_event] Provider for initializing opensearchservice domains",
        )
        self.secret.grant_read(on_event_handler)

        is_complete_handler = cdk_lambda.Function(
            self,
            "is_complete",
            code=PackageAssetCode.from_python_inline(
                IS_COMPLETE_CODE, requirements=["requests==2.26.0"]
            ),
            handler="index.handler",
            runtime=cdk_lambda.Runtime.PYTHON_3_8,
            environment={
                "OPENSEARCH_ENDPOINT": f"https://{self.domain.domain_endpoint}",
                "OPENSEARCH_USERNAME": self.username,
                "OPENSEARCH_SECRET": self.secret.secret_name,
            },
            description="[CustomOpenSearchServiceProvider:is_complete] Provider for initializing opensearchservice domains and runs initializer [check for errors at deployment]",
            timeout=cdk.Duration.minutes(3),
        )
        self.secret.grant_read(is_complete_handler)

        self.post_load = cdk_custom.Provider(
            self,
            "post_load_provider",
            on_event_handler=on_event_handler,
            is_complete_handler=is_complete_handler,
            query_interval=cdk.Duration.minutes(1),
            total_timeout=cdk.Duration.hours(2),
        )


class Post(constructs.Construct):
    def __init__(
        self,
        scope: constructs.Construct,
        id: str,
        *,
        resource_path: str,
        enhaceddomain: EnhacedDomain,
        body: str,
    ) -> None:
        super().__init__(scope, id)

        self.resource_path = resource_path
        self.enhaceddomain = enhaceddomain

        cdk.CustomResource(
            self,
            "custom_resource",
            service_token=enhaceddomain.post_load.service_token,
            properties={
                "ResourcePath": self.resource_path,
                "Body": body,
            },
            removal_policy=cdk.RemovalPolicy.DESTROY,
            resource_type="Custom::OpenSearchEnhacedDomainPost",
        )


class Resource(Post):
    def __init__(
        self,
        scope: constructs.Construct,
        id: str,
        *,
        resource_path: str,
        enhaceddomain: EnhacedDomain,
        post_load_body: str,
    ) -> None:
        super().__init__(
            scope,
            id,
            resource_path=resource_path,
            enhaceddomain=enhaceddomain,
            body=post_load_body,
        )

    @property
    def endpoint(self) -> str:
        return f"https://{self.enhaceddomain.domain.domain_endpoint}/{self.resource_path}"

    @property
    def username(self) -> str:
        return self.enhaceddomain.username

    @property
    def secret_name(self) -> str:
        return self.enhaceddomain.secret.secret_name


ON_EVENT_CODE = """
def handler(event, context):
    return { }
"""

IS_COMPLETE_CODE = """
import os
import urllib.parse
import base64
import json
import boto3
import requests

OPENSEARCH_ENDPOINT = os.getenv("OPENSEARCH_ENDPOINT")
OPENSEARCH_USERNAME = os.getenv("OPENSEARCH_USERNAME")
OPENSEARCH_SECRET = os.getenv("OPENSEARCH_SECRET")

smclient = boto3.client("secretsmanager")
secret_value = smclient.get_secret_value(SecretId=OPENSEARCH_SECRET)
OPENSEARCH_PASSWORD = secret_value["SecretString"]


class FatalError(Exception):
    pass


def handler(event, context):
    # Do nothing if it's not creating
    if event['RequestType'] not in ('Create', 'Update'):
        print('Do nothing')
        return { 'IsComplete': True }

    token = base64.b64encode(f'{OPENSEARCH_USERNAME}:{OPENSEARCH_PASSWORD}'.encode()).decode()
    headers = {
        'Authorization': f'Basic {token}'
    }

    try:
        response = requests.get(
            urllib.parse.urljoin(OPENSEARCH_ENDPOINT, "_cluster/health"),
            headers=headers
        )
        if response.status_code == 401:
            raise FatalError(f"status_code: {response.status_code}")

        cluster_health = response.json()
        cluster_status = cluster_health.get('status', 'Unknown')

        is_stable = cluster_status in ['green', 'yellow']
        if is_stable:
            resource_properties = event['ResourceProperties']

            resource_path = resource_properties["ResourcePath"]
            body = resource_properties["Body"]

            response = requests.put(
                urllib.parse.urljoin(OPENSEARCH_ENDPOINT, index),
                json=json.loads(initializer),
                headers=headers
            )

            if response.status_code >= 200 and response.status_code < 300:
                print('[INFO] Initialized:', index, 'with', json.dumps(initializer))
            else:
                print('[ERROR] Failed:', index, 'with', json.dumps(initializer))

            return { "IsComplete": True }
    except requests.exceptions.RequestException:
        pass

    print("Cluster is not yet stable")

    return { "IsComplete": False }
"""
