import abc

from aws_cdk import core as cdk
from aws_cdk import aws_lambda as lambda_


class IChannel:
    pass


class ChannelBase(cdk.Construct, IChannel):
    pass
