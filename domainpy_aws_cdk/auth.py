import constructs
import aws_cdk as cdk
import aws_cdk.aws_iam as cdk_iam
import aws_cdk.aws_lambda as cdk_lambda
import aws_cdk.aws_cognito as cdk_cognito


class ClientPool(constructs.Construct):
    def __init__(
        self,
        scope: constructs.Construct,
        id: str,
        *,
        token_len: int = 4,
        max_attemps: int = 3
    ) -> None:
        super().__init__(scope, id)

        pre_signup_function = cdk_lambda.Function(
            self,
            "pre_signup_function",
            code=cdk_lambda.AssetCode.from_inline(PRE_SIGNUP_CODE),
            runtime=cdk_lambda.Runtime.PYTHON_3_8,
            handler="index.handler",
        )

        define_auth_challenge_function = cdk_lambda.Function(
            self,
            "define_auth_challenge_function",
            code=cdk_lambda.AssetCode.from_inline(DEFINE_AUTH_CHALLENGE),
            runtime=cdk_lambda.Runtime.PYTHON_3_8,
            handler="index.handler",
            environment={"MAX_ATTEMPTS": str(max_attemps)},
        )

        create_auth_challenge_function = cdk_lambda.Function(
            self,
            "create_auth_challenge_function",
            code=cdk_lambda.AssetCode.from_inline(CREATE_AUTH_CHALLENGE_CODE),
            runtime=cdk_lambda.Runtime.PYTHON_3_8,
            handler="index.handler",
            initial_policy=[
                cdk_iam.PolicyStatement(
                    actions=["sns:Publish"],
                    not_resources=["arn:aws:sns:*:*:*"],
                )
            ],
            environment={"TOKEN_LEN": str(token_len)},
        )

        verify_auth_challenge_function = cdk_lambda.Function(
            self,
            "verify_auth_challenge_function",
            code=cdk_lambda.AssetCode.from_inline(VERIFY_AUTH_CHALLENGE_CODE),
            runtime=cdk_lambda.Runtime.PYTHON_3_8,
            handler="index.handler",
        )

        self.user_pool = cdk_cognito.UserPool(
            self,
            "user_pool",
            sign_in_aliases=cdk_cognito.SignInAliases(
                username=True, phone=True, email=True
            ),
            lambda_triggers=cdk_cognito.UserPoolTriggers(
                pre_sign_up=pre_signup_function,
                define_auth_challenge=define_auth_challenge_function,
                create_auth_challenge=create_auth_challenge_function,
                verify_auth_challenge_response=verify_auth_challenge_function,
            ),
            self_sign_up_enabled=True,
            auto_verify=cdk_cognito.AutoVerifiedAttrs(phone=True, email=True),
            account_recovery=cdk_cognito.AccountRecovery.EMAIL_ONLY,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

    def add_client(self, id: str) -> None:
        self.user_pool.add_client(id, auth_flows=cdk_cognito.AuthFlow(custom=True))


PRE_SIGNUP_CODE = """
def handler(event, context):
    event["response"]["autoConfirmUser"] = True
    event["response"]["autoVerifyPhone"] = True
    return event
"""

DEFINE_AUTH_CHALLENGE = """
import os

MAX_ATTEMPTS = int(os.getenv('MAX_ATTEMPTS'))

def handler(event, context):
    request = event["request"]
    response = event["response"]

    if has_session(request) and challenge_passed(request):
        response["failAuthentication"] = False
        response["issueTokens"] = True
    elif has_session(request) and attemps_exhausted(request):
        response["failAuthentication"] = True
        response["issueTokens"] = False
    else:
        response["challengeName"] = "CUSTOM_CHALLENGE"
        response["failAuthentication"] = False
        response["issueTokens"] = False

    return event


def has_session(request):
    return "session" in request and len(request["session"]) > 0


def attemps_exhausted(request):
    return len(request["session"]) == MAX_ATTEMPTS


def challenge_passed(request):
    return any(attemp["challengeResult"] == True for attemp in request["session"])

"""

CREATE_AUTH_CHALLENGE_CODE = """
import os
import secrets
import boto3

sns = boto3.client("sns")

TOKEN_LEN = int(os.getenv("TOKEN_LEN"))

ALPHABET = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']

def handler(event, context):
    # event["request"]["callerContext"]["clientId"]
    request = event["request"]
    response = event["response"]

    if not has_session(request):
        phonenumber = request["userAttributes"]["phone_number"]
        token = generate_token(TOKEN_LEN)
        send_token(phonenumber, token)
    else:
        previous_challenge = request["session"][-1]
        token = previous_challenge["challengeMetadata"]

    # Add to parameters for "Verify Auth Challenge"
    response["privateChallengeParameters"] = { "expectedAnswer": token }

    # Add to session for the next "Create Auth Challenge" invocation
    response["challengeMetadata"] = token

    return event

def has_session(request):
    return (
        "session" in request and len(request["session"]) > 0
    )

def generate_token(length):
    return "".join(secrets.choice(ALPHABET) for _ in range(length))

def send_token(phonenumber, token):
    sns.publish(
        PhoneNumber=phonenumber, 
        Message=f"{token} es tu codigo de MyMamaChef",
        MessageAttributes={
            "AWS.SNS.SMS.SMSType": {
                "DataType": "String",
                "StringValue": "Transactional"
            }
        }
    )
"""

VERIFY_AUTH_CHALLENGE_CODE = """
def handler(event, context):
    request = event["request"]
    response = event["response"]

    challengeAnswer = request["challengeAnswer"]
    expectedAnswer = request["privateChallengeParameters"]["expectedAnswer"]
    if challengeAnswer == expectedAnswer:
        response["answerCorrect"] = True
    else:
        response["answerCorrect"] = False

    return event
"""
