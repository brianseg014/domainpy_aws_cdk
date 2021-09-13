import os
import typing
import json
import tempfile
import shutil

from aws_cdk import core as cdk
from aws_cdk import aws_iam as iam
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as events_targets
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_python as lambda_python
from aws_cdk import aws_lambda_event_sources as lambda_sources
from aws_cdk import aws_sqs as sqs
from aws_cdk import aws_secretsmanager as secretsmanager
from aws_cdk import aws_elasticsearch as elasticsearch
from aws_cdk import custom_resources

from domainpy_aws_cdk.constructs.utils import DomainpyLayerVersion


class DynamoDBProjection(cdk.Construct):

    def __init__(self, scope: cdk.Construct, construct_id: str, *, projection_id: str, parent_projection_id: typing.Optional[str] = None):
        super().__init__(scope, construct_id)

        self.table = dynamodb.Table(self, 'table',
            partition_key={ 'name': projection_id, 'type': dynamodb.AttributeType.STRING },
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.DESTROY
        )

        if parent_projection_id is not None:
            self.table.add_global_secondary_index(
                index_name='by_parent',
                partition_key={ 'name': parent_projection_id, 'type': dynamodb.AttributeType.STRING },
                sort_key={ 'name': projection_id, 'type': dynamodb.AttributeType.STRING },
                projection_type=dynamodb.ProjectionType.ALL
            )


class DynamoDBProjector(cdk.Construct):

    def __init__(
        self, 
        scope: cdk.Construct, 
        construct_id: str, 
        *, 
        entry: str,
        domain_subscriptions: typing.Dict[str, typing.Sequence[str]],
        projection: DynamoDBProjection,
        share_prefix: str,
        index: str = 'app',
        handler: str = 'handler'
    ):
        super().__init__(scope, construct_id)

        domain_bus = events.EventBus.from_event_bus_name(
            self, 'domain-bus', cdk.Fn.import_value(f'{share_prefix}DomainBusName')
        )
        integration_bus = events.EventBus.from_event_bus_name(
            self, 'integration-bus', cdk.Fn.import_value(f'{share_prefix}IntegrationBusName')
        )

        self.dead_letter_queue = sqs.Queue(self, "dlq")
        self.queue = sqs.Queue(self, "queue",
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=20,
                queue=self.dead_letter_queue
            ),
            visibility_timeout=cdk.Duration.seconds(30),
            receive_message_wait_time=cdk.Duration.seconds(20)
        )

        if len(domain_subscriptions) > 0:
            for domain_context,domain_events_names in domain_subscriptions.items():
                events.Rule(self, f'{domain_context}-domain-rule',
                    event_bus=domain_bus,
                    event_pattern=events.EventPattern(
                        detail_type=domain_events_names,
                        source=[domain_context]
                    ),
                    targets=[
                        events_targets.SqsQueue(
                            self.queue, message=events.RuleTargetInput.from_event_path('$.detail')
                        )
                    ]
                )

        domainpy_layer = DomainpyLayerVersion(self, 'domainpy')
        self.microservice = lambda_python.PythonFunction(self, 'microservice',
            entry=entry,
            runtime=lambda_.Runtime.PYTHON_3_8,
            index=index,
            handler=handler,
            environment={
                'DYNAMODB_TABLE_NAME': projection.table.table_name,
                'INTEGRATION_EVENT_BUS_NAME': integration_bus.event_bus_name
            },
            memory_size=512,
            layers=[domainpy_layer],
            timeout=cdk.Duration.seconds(10),
            tracing=lambda_.Tracing.ACTIVE,
            description='[PROJECTOR] Projects domain events into projection'
        )
        self.microservice.add_event_source(lambda_sources.SqsEventSource(self.queue))
        projection.table.grant_read_write_data(self.microservice)
        integration_bus.grant_put_events_to(self.microservice)


class ElasticSearchInitializerProps:
    def __init__(self, index: str, doc: str) -> None:
        self.index = index
        self.doc = doc
        

class ElasticSearchProjection(cdk.Construct):

    def __init__(
        self, 
        scope: cdk.Construct, 
        construct_id: str, 
        *, 
        initializers: typing.Optional[typing.Sequence[ElasticSearchInitializerProps]] = None
    ) -> None:
        super().__init__(scope, construct_id)

        self.domain_credentials = secretsmanager.Secret(self, 'credentials', 
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{ "username": "mmc" }',
                generate_string_key='password'
            ),
            removal_policy=cdk.RemovalPolicy.DESTROY
        )

        self.domain = elasticsearch.Domain(self, 'domain',
            version=elasticsearch.ElasticsearchVersion.V7_10,
            capacity=elasticsearch.CapacityConfig(
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
            fine_grained_access_control=elasticsearch.AdvancedSecurityOptions(
                master_user_name=self.domain_credentials.secret_value_from_json('username').to_string(),
                master_user_password=self.domain_credentials.secret_value_from_json('password')
            ),
            encryption_at_rest=elasticsearch.EncryptionAtRestOptions(
                enabled=True
            ),
            node_to_node_encryption=True,
            enable_version_upgrade=True,
            enforce_https=True,
            removal_policy=cdk.RemovalPolicy.DESTROY
        )

        if initializers is not None:
            ElasticSearchInitializer(self, 'initializer',
                url=f'https://{self.domain.domain_endpoint}',
                initializers=initializers,
                domain_secret=self.domain_credentials
            )


class ElasticSearchProjector(cdk.Construct):
    
    def __init__(
        self,
        scope: cdk.Construct,
        construct_id: str,
        *,
        entry: str,
        domain_subscriptions: typing.Dict[str, typing.Sequence[str]],
        projection: ElasticSearchProjection,
        share_prefix: str,
        index: str = 'app',
        handler: str = 'handler'
    ) -> None:
        super().__init__(scope, construct_id)

        domain_bus = events.EventBus.from_event_bus_name(
            self, 'domain-bus', cdk.Fn.import_value(f'{share_prefix}DomainBusName')
        )
        integration_bus = events.EventBus.from_event_bus_name(
            self, 'integration-bus', cdk.Fn.import_value(f'{share_prefix}IntegrationBusName')
        )

        self.dead_letter_queue = sqs.Queue(self, "dlq")
        self.queue = sqs.Queue(self, "queue",
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=20,
                queue=self.dead_letter_queue
            ),
            visibility_timeout=cdk.Duration.seconds(30),
            receive_message_wait_time=cdk.Duration.seconds(20)
        )

        if len(domain_subscriptions) > 0:
            for domain_context,domain_events_names in domain_subscriptions.items():
                events.Rule(self, f'{domain_context}-domain-rule',
                    event_bus=domain_bus,
                    event_pattern=events.EventPattern(
                        detail_type=domain_events_names,
                        source=[domain_context]
                    ),
                    targets=[
                        events_targets.SqsQueue(
                            self.queue, message=events.RuleTargetInput.from_event_path('$.detail')
                        )
                    ]
                )

        domainpy_layer = DomainpyLayerVersion(self, 'domainpy')
        self.microservice = lambda_python.PythonFunction(self, 'microservice',
            entry=entry,
            runtime=lambda_.Runtime.PYTHON_3_8,
            index=index,
            handler=handler,
            environment={
                'ELASTICSEARCH_URL': f'https://{projection.domain.domain_endpoint}',
                'ELASTICSEARCH_SECRET_NAME': projection.domain_credentials.secret_name,
                'INTEGRATION_EVENT_BUS_NAME': integration_bus.event_bus_name
            },
            memory_size=512,
            layers=[domainpy_layer],
            timeout=cdk.Duration.seconds(10),
            tracing=lambda_.Tracing.ACTIVE,
            description='[PROJECTOR] Projects domain events into projection'
        )
        self.microservice.add_event_source(lambda_sources.SqsEventSource(self.queue))
        projection.domain_credentials.grant_read(self.microservice)
        integration_bus.grant_put_events_to(self.microservice)


class ElasticSearchInitializer(cdk.Construct):

    def __init__(
        self, 
        scope: cdk.Construct, 
        construct_id: str, 
        *,
        url: str,
        initializers: typing.Optional[typing.Sequence[ElasticSearchInitializerProps]],
        domain_secret: secretsmanager.Secret
    ) -> None:
        super().__init__(scope, construct_id)

        cdk.CustomResource(self, 'resource',
            service_token=ElasticSearchInitializerProvider.get_or_create(self),
            resource_type='Custom::ElasticSearchInitializer',
            properties={
                'url': url,
                'initializers': json.dumps([
                    (i.index,i.doc) for i in initializers
                ]),
                'secret_name': domain_secret.secret_name
            }
        )


class ElasticSearchInitializerProvider(cdk.Construct):

    @classmethod
    def get_or_create(cls, scope: cdk.Construct) -> str:
        stack = cdk.Stack.of(scope)
        x = ElasticSearchInitializerProvider(stack, 'esinitializer')
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


ON_EVENT_CODE = \
"""
def handler(event, context):
    print(event)
    return { }
"""

IS_COMPLETE_CODE = \
"""
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
