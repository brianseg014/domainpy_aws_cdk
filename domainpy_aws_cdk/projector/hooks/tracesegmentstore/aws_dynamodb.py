
from aws_cdk import core as cdk

from domainpy_aws_cdk.projector.base import IProjector, ITraceSegmentStoreHook
from domainpy_aws_cdk.projector.aws_lambda import LambdaProjectorBase
from domainpy_aws_cdk.tracestore.aws_dynamodb import DynamoDBTableTraceSegmentStore


class DynamoDBTableTraceSegmentStoreHook(ITraceSegmentStoreHook):

    def __init__(
        self,
        trace_segment_store: DynamoDBTableTraceSegmentStore
    ) -> None:
        self.trace_segment_store = trace_segment_store

    def bind(self, projector: IProjector):
        if isinstance(projector, LambdaProjectorBase):
            self._bind_lambda_context(projector)
        else:
            raise cdk.ValidationError('projector-tracesegmentstore incompatible')

    def _bind_lambda_context(self, projector: LambdaProjectorBase):
        function = projector.microservice

        function.add_environment('TRACE_SEGMENT_STORE_SERVICE', 'AWS::DynamoDB::Table')
        function.add_environment('TRACE_SEGMENT_STORE_TABLE_NAME', self.trace_segment_store.table.table_name)
        self.trace_segment_store.table.grant_read_write_data(function)
