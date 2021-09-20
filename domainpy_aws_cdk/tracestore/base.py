
from aws_cdk import core as cdk


class ITraceStore:
    pass


class TraceStoreBase(cdk.Construct, ITraceStore):
    pass


class ITraceSegmentStore:
    pass


class TraceSegmentStoreBase(cdk.Construct, ITraceSegmentStore):
    pass
