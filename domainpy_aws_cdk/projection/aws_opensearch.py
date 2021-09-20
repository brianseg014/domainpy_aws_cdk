import os
import json
import typing
import tempfile

from aws_cdk import core as cdk
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_python as lambda_python
from aws_cdk import aws_opensearchservice as opensearch
from aws_cdk import aws_secretsmanager as secretsmanager
from aws_cdk import custom_resources

from domainpy_aws_cdk.projection.base import ProjectionBase


class OpenSearchService(cdk.Construct):

    def __init__(self, scope: cdk.Construct, id: str) -> None:
        super().__init__(scope, id)

        self.domain_credentials = secretsmanager.Secret(self, 'credentials', 
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{ "username": "mmc" }',
                generate_string_key='password'
            ),
            removal_policy=cdk.RemovalPolicy.DESTROY
        )

        self.domain = opensearch.Domain(self, 'domain',
            version=opensearch.EngineVersion.OPENSEARCH_1_0,
            capacity=opensearch.CapacityConfig(
                data_node_instance_type='t3.small.elasticsearch',
                data_nodes=1
            ),
            access_policies=[
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=['es:*'],
                    resources=['*'],
                    principals=[iam.AnyPrincipal()]
                )
            ],
            fine_grained_access_control=opensearch.AdvancedSecurityOptions(
                master_user_name=self.domain_credentials.secret_value_from_json('username').to_string(),
                master_user_password=self.domain_credentials.secret_value_from_json('password')
            ),
            encryption_at_rest=opensearch.EncryptionAtRestOptions(
                enabled=True
            ),
            node_to_node_encryption=True,
            enable_version_upgrade=True,
            enforce_https=True,
            removal_policy=cdk.RemovalPolicy.DESTROY
        )


class OpenSearchInitializerProps:
    def __init__(self, index: str, doc: str) -> None:
        self.index = index
        self.doc = doc


class OpenSearchDomainProjection(ProjectionBase):

    def __init__(
        self,
        scope: cdk.Construct,
        id: str,
        *,
        index: str,
        open_search_service: OpenSearchService,
        initializers: typing.Optional[typing.Sequence[OpenSearchInitializerProps]] = None
    ) -> None:
        super().__init__(scope, id)
 
        self.index = index
        self.open_search_service = open_search_service

        if initializers is not None:
            OpenSearchInitializer(self, 'initializer',
                url=f'https://{open_search_service.domain.domain_endpoint}',
                initializers=initializers,
                domain_secret=open_search_service.domain_credentials
            )


class OpenSearchInitializer(cdk.Construct):

    def __init__(
        self, 
        scope: cdk.Construct, 
        construct_id: str, 
        *,
        url: str,
        initializers: typing.Sequence[OpenSearchInitializerProps],
        domain_secret: secretsmanager.Secret
    ) -> None:
        super().__init__(scope, construct_id)

        cdk.CustomResource(self, 'resource',
            service_token=OpenSearchInitializerProvider.get_or_create(self),
            resource_type='Custom::OpenSearchInitializer',
            properties={
                'url': url,
                'initializers': json.dumps([
                    (i.index,i.doc) for i in initializers
                ]),
                'secret_name': domain_secret.secret_name
            }
        )


class OpenSearchInitializerProvider(cdk.Construct):

    @classmethod
    def get_or_create(cls, scope: cdk.Construct) -> str:
        stack = cdk.Stack.of(scope)
        x = OpenSearchInitializerProvider(stack, 'esinitializer')
        return x.provider.service_token

    def __init__(self, scope: cdk.Construct, construct_id: str) -> None:
        super().__init__(scope, construct_id)

        on_event = lambda_.Function(self, 'on-event',
            code=lambda_.Code.from_inline(ON_EVENT_CODE),
            runtime=lambda_.Runtime.PYTHON_3_8,
            handler='index.handler',
            description="AWS CDK ElasticSearch initializer provider async on event"
        )

        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, 'requirements.txt'), 'w') as file:
                file.write('boto3==1.18.18\n')
                file.write('requests==2.26.0\n')

            with open(os.path.join(tmp, 'index.py'), 'w') as file:
                file.write(IS_COMPLETE_CODE)

            is_complete = lambda_python.PythonFunction(self, 'is-complete',
                entry=tmp,
                runtime=lambda_.Runtime.PYTHON_3_8,
                handler='handler',
                initial_policy=[
                    iam.PolicyStatement(
                        resources=['*'],
                        actions=[
                            "secretsmanager:GetResourcePolicy",
                            "secretsmanager:GetSecretValue",
                            "secretsmanager:DescribeSecret",
                            "secretsmanager:ListSecretVersionIds"
                        ]
                    )   
                ],
                timeout=cdk.Duration.minutes(2),
                description="AWS CDK Domain initializer provider async is complete"
            )

        self.provider = custom_resources.Provider(self, 'provider',
            on_event_handler=on_event,
            is_complete_handler=is_complete,
            query_interval=cdk.Duration.minutes(3),
            total_timeout=cdk.Duration.hours(2)
        )

ON_EVENT_CODE = """
def handler(event, context):
    print(event)
    return { }
"""

IS_COMPLETE_CODE = """
import json
import boto3
import base64
import requests
import urllib.parse

def handler(event, context):
    print(event)

    # Do nothing if it's not creating
    if event['RequestType'] not in ('Create', 'Update'):
        print('Do nothing')
        return { 'IsComplete': True }

    props = event['ResourceProperties']
    print('PROPS', props)

    url = props['url']
    secret_name = props['secret_name']
    initializers = json.loads(props['initializers'])

    headers = get_headers(secret_name)

    try:
        requests.get(url, headers=headers)
    except requests.exceptions.MissingSchema:
        print('Malformed url', url)
        return { 'IsComplete': False }
    except requests.exceptions.ConnectionError:
        print('connection error')
        return { 'IsComplete': False }

    r = requests.get(
        urllib.parse.urljoin(url, '_cluster/health'),
        headers=headers
    )
    if r.status_code == 401:
        raise Exception('Unauthorized')

    print('HEATLH', r.text, r.status_code)
    cluster_health = r.json()
    cluster_status = cluster_health.get('status', 'Unknown')
    print('Cluster status:', cluster_status)
    
    is_stable = cluster_status in ['green', 'yellow']
    if is_stable:
        for index,initializer in initializers:
            try:
                requests.put(
                    urllib.parse.urljoin(url, index),
                    json=initializer,
                    headers=headers
                )
                print('[INFO] Initialized index', index, 'with', json.dumps(initializer))
            except Exception as error:
                print('[Error] Fail initializating index', index, 'with', json.dumps(initializer), ':', repr(error))

    return { 'IsComplete': is_stable }

def get_headers(secret_name):
    token = get_token(secret_name)
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Basic {token}'
        # 'Authorization': f'Basic bW1jOkFiYzEyMyoq'
    }
    return headers

def get_token(secret_name):
    secretsmanager = boto3.client('secretsmanager')
    credentials = secretsmanager.get_secret_value(SecretId=secret_name)
    secret = json.loads(credentials['SecretString'])
    username = secret['username']
    password = secret['password']
    
    token = base64.b64encode(f'{username}:{password}'.encode()).decode()
    return token
"""
