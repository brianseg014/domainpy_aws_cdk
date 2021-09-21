
from aws_cdk import core as cdk

from domainpy_aws_cdk.context.base import IContext, ITraceSegmentStoreHook
from domainpy_aws_cdk.context.aws_lambda import LambdaContextBase
from domainpy_aws_cdk.tracestore.aws_dynamodb import DynamoDBTableTraceSegmentStore


class DynamoDBTableTraceSegmentStoreHook(ITraceSegmentStoreHook):

    def __init__(
        self,
        trace_segment_store: DynamoDBTableTraceSegmentStore
    ) -> None:
        self.trace_segment_store = trace_segment_store

    def bind(self, context: IContext):
        if isinstance(context, LambdaContextBase):
            self._bind_lambda_context(context)
        else:
            raise cdk.ValidationError('context-tracesegmentstore incompatible')

    def _bind_lambda_context(self, context: LambdaContextBase):
        function = context.function

        function.add_environment('TRACE_SEGMENT_STORE_SERVICE', 'AWS::DynamoDB::Table')
        function.add_environment('TRACE_SEGMENT_STORE_TABLE_NAME', self.trace_segment_store.table.table_name)
        self.trace_segment_store.table.grant_read_write_data(function)
