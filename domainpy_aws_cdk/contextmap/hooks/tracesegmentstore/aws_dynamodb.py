
from aws_cdk import core as cdk

from domainpy_aws_cdk.contextmap.base import IContextMap, ITraceSegmentStoreHook
from domainpy_aws_cdk.contextmap.aws_lambda import LambdaContextMapBase
from domainpy_aws_cdk.tracestore.aws_dynamodb import DynamoDBTableTraceSegmentStore


class DynamoDBTableTraceSegmentStoreHook(ITraceSegmentStoreHook):

    def __init__(
        self,
        trace_segment_store: DynamoDBTableTraceSegmentStore
    ) -> None:
        self.trace_segment_store = trace_segment_store

    def bind(self, context_map: IContextMap):
        if isinstance(context_map, LambdaContextMapBase):
            self._bind_lambda_context(context_map)
        else:
            raise cdk.ValidationError('contextmap-tracesegmentstore incompatible')

    def _bind_lambda_context(self, context_map: LambdaContextMapBase):
        function = context_map.microservice

        function.add_environment('TRACE_SEGMENT_STORE_SERVICE', 'AWS::DynamoDB::Table')
        function.add_environment('TRACE_SEGMENT_STORE_TABLE_NAME', self.trace_segment_store.table.table_name)
        self.trace_segment_store.table.grant_read_write_data(function)
