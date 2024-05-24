import {
  Stack,
  StackProps,
  aws_s3 as s3,
  aws_sns as sns,
  aws_lambda as lambda,
  aws_iam as iam,
  aws_s3_notifications as s3n,
  aws_dynamodb as dynamodb,
  aws_lambda_event_sources as lambdaEventSources,
  aws_ec2 as ec2,
  aws_elasticloadbalancingv2 as elbv2,
  aws_ecs as ecs,
  aws_sagemaker as sagemaker
} from "aws-cdk-lib";

import { Duration } from "aws-cdk-lib";
import { Period } from "aws-cdk-lib/aws-apigateway";
import * as sqs from "aws-cdk-lib/aws-sqs";
import {
  DynamoEventSource,
  SqsEventSource,
} from "aws-cdk-lib/aws-lambda-event-sources";
import { Construct } from "constructs";
import * as cdk from "aws-cdk-lib";
import * as subs from "aws-cdk-lib/aws-sns-subscriptions";
import * as sm from "aws-cdk-lib/aws-sagemaker";

export class QueryProStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    // Define Sagemaker Endpoint
    const endpoint = new sagemaker.CfnEndpoint(this, "SageMakerEndpoint", {
      endpointConfigName: 'sagemaker-epc-1715029537755',
      endpointName: "jumpstart-dft-hf-llm-mixtral-8x7b-instruct-v2", // Replace with your Endpoint Name
      // Additional properties as needed
    });

    // Define the Lambda function
    const myChatbot = new lambda.Function(this, "MyFunction", {
      runtime: lambda.Runtime.PYTHON_3_10, // Choose the runtime environment
      code: lambda.Code.fromAsset("Lambda"), // Specify the directory of your Lambda code
      handler: "chatbot.handler", // File and method name (index.js and exports.handler)
    });

    // Define the IAM policy statements for the necessary services
    const policyStatement = new iam.PolicyStatement({
      actions: [
        "s3:*", // Adjust according to your needs
        "dynamodb:*", // Adjust according to your needs
        "sagemaker:*", // Adjust according to your needs
      ],
      resources: ["*"], // It's recommended to specify more restrictive resource ARNs
    });

    // Attach the policy to the Lambda function
    myChatbot.addToRolePolicy(policyStatement);

    // Create an S3 bucket
    const myBucket = new s3.Bucket(this, "MyBucket", {
      versioned: true,
      encryption: s3.BucketEncryption.S3_MANAGED,
      removalPolicy: cdk.RemovalPolicy.DESTROY, // NOT recommended for production code
    });

    // S3 sns topic from S3->SNS->SQS  step 1
    const s3_topic = new sns.Topic(
      this,
      "uploaded-step-1-prod-query-pro-dev-v6-v2-s3-sns-topic"
    );
    // S3 queue from S3->SNS->SQS  step 2
    const s3_queue = new sqs.Queue(
      this,
      "uploaded-step-2-prod-query-pro-dev-v6-v2-s3-sqs-queue",
      {
        retentionPeriod: cdk.Duration.days(10),
        visibilityTimeout: cdk.Duration.seconds(1000),
      }
    );
    // adding s3 queue to s3 sns topic
    // subscribe queue to topic
    s3_topic.addSubscription(new subs.SqsSubscription(s3_queue));

    //dynamoDB
    const table = new dynamodb.Table(this, "caseDetailsTable", {
      partitionKey: { name: "CaseNumber", type: dynamodb.AttributeType.STRING },
      tableName: "caseDetailsTableV2", // Updated name
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      encryption: dynamodb.TableEncryption.AWS_MANAGED,
    });

    // Create an S3 bucket

    // Define an IAM role for Lambda
    const lambdaRole = new iam.Role(this, "LambdaExecutionRole", {
      assumedBy: new iam.ServicePrincipal("lambda.amazonaws.com"),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName(
          "service-role/AWSLambdaBasicExecutionRole"
        ),
        iam.ManagedPolicy.fromAwsManagedPolicyName(
          "service-role/AWSLambdaVPCAccessExecutionRole"
        ),
      ],
    });

    // Lambda Function Triggered by S3 Upload

    // notification topic sfter the job is complete it will be trigered by textract
    const notification_topic = new sns.Topic(
      this,
      "dev-blocks-textract-sns-topic-v6-v2"
    );
    // role of textract
    const textractServiceRole = new iam.Role(this, "TextractServiceRole", {
      assumedBy: new iam.ServicePrincipal("textract.amazonaws.com"),
    });
    textractServiceRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        resources: [notification_topic.topicArn],
        actions: ["sns:Publish"],
      })
    );
    // S3 pipeline to extract text
    const textract_func = new lambda.Function(this, "s3Trigger", {
      runtime: lambda.Runtime.PYTHON_3_10,
      code: lambda.Code.fromAsset("Lambda"),
      handler: "s3Trigger.handler",
      timeout: Duration.minutes(15),
      environment: {
        SNS_TOPIC_ARN: notification_topic.topicArn,
        TEXTRACT_ROLE_ARN: textractServiceRole.roleArn,
        BUCKET_NAME: myBucket.bucketName,
      },
    });

    textract_func.addToRolePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          "logs:*",
          "apigateway:*",
          "s3:*",
          "textract:*",
          "sns:*",
          "sqs:*",
          "dynamodb:*",
          "bedrock:*",
          "sagemaker:InvokeEndpoint",
        ],
        resources: ["*"],
      })
    );
    // textract_func triggered by s3_queue that is connected by S3 topic upload
    textract_func.addEventSource(new SqsEventSource(s3_queue));
    // Queue that will be used by Complete Job Textract
    const s3_textrract_complete_queue = new sqs.Queue(
      this,
      "query_pro-dev-v6-v2-s3-textrract-complete-sqs-queue",
      {
        retentionPeriod: cdk.Duration.days(10),
        visibilityTimeout: cdk.Duration.seconds(1000),
      }
    );

    // Set S3 upload as an event source for the Lambda function
    // adding SNS to S3 object created notification with suffix filters
    myBucket.addEventNotification(
      s3.EventType.OBJECT_CREATED,
      new s3n.SnsDestination(s3_topic),
      {
        suffix: ".pdf",
      }
    );
    // notificatin SNS topic subsciption to s3_textrract_complete_queue
    notification_topic.addSubscription(
      new subs.SqsSubscription(s3_textrract_complete_queue)
    );
    // s3_textrract_complete_queue as event source for lambda function
    // lambda function
    const textract_complete_func = new lambda.Function(
      this,
      "query_pro_prod_dev_v6_v2_textract_complete_func",
      {
        runtime: lambda.Runtime.PYTHON_3_10,
        code: lambda.Code.fromAsset("Lambda"),
        handler: "snsTrigger.handler",
        timeout: Duration.minutes(15),
        environment: {
          BUCKET_NAME: myBucket.bucketName,
          SAGEMAKER_ENDPOINT_NAME:
            "jumpstart-dft-hf-llm-mixtral-8x7b-instruct-v2",
        },
      }
    );
    textract_complete_func.addToRolePolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          "logs:*",
          "apigateway:*",
          "s3:*",
          "textract:*",
          "sns:*",
          "sqs:*",
          "dynamodb:*",
          "bedrock:*",
          "sagemaker:InvokeEndpoint",
        ],
        resources: ["*"],
      })
    );
    // adding trigger from the SQS that is triggered from SNS topic of completion
    textract_complete_func.addEventSource(
      new SqsEventSource(s3_textrract_complete_queue)
    );

    const vpc = ec2.Vpc.fromLookup(this, "ExistingVpc", {
      vpcId: "vpc-0d86631672278708e", // Replace with your VPC ID
    });

    // Import existing subnets
    const subnets = vpc.selectSubnets({
      subnetFilters: [
        ec2.SubnetFilter.byIds(["subnet-0bf4dab65864fe6d3", "subnet-0577d87588a7b373f"]), // Replace with your Subnet IDs
      ],
    });

    // Import existing security group
    const securityGroup = ec2.SecurityGroup.fromSecurityGroupId(this, "ExistingSecurityGroup", "sg-01602a563435263e3"); // Replace with your Security Group ID

    // Import existing load balancer
    const loadBalancer = elbv2.ApplicationLoadBalancer.fromApplicationLoadBalancerAttributes(this, "ExistingLoadBalancer", {
      loadBalancerArn: "arn:aws:elasticloadbalancing:us-east-1:500608964291:loadbalancer/app/mcao-lb/e530a024f9ea0085", // Replace with your Load Balancer ARN
      securityGroupId: securityGroup.securityGroupId,
    });


    const cluster = new ecs.Cluster(this, "EcsCluster", {
      vpc,
      clusterName: "ganesh_3_cluster",
    });

    const taskRole = new iam.Role(this, "TaskRole", {
      assumedBy: new iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName("service-role/AmazonEC2ContainerServiceforEC2Role"),
        iam.ManagedPolicy.fromAwsManagedPolicyName("service-role/AmazonEC2ContainerServiceRole"),
        iam.ManagedPolicy.fromAwsManagedPolicyName("AmazonECS_FullAccess"),
      ],
    });

    const executionRole = new iam.Role(this, "ExecutionRole", {
      assumedBy: new iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName("EC2InstanceProfileForImageBuilderECRContainerBuilds"),
        iam.ManagedPolicy.fromAwsManagedPolicyName("service-role/AmazonECSTaskExecutionRolePolicy"),
        iam.ManagedPolicy.fromAwsManagedPolicyName("AmazonBedrockFullAccess"),
        iam.ManagedPolicy.fromAwsManagedPolicyName("AmazonS3FullAccess"),
      ],
    });

    const taskDefinition = new ecs.FargateTaskDefinition(this, "TaskDef", {
      memoryLimitMiB: 3072,
      cpu: 1024,
      taskRole,
      executionRole
    });

    const container = taskDefinition.addContainer("mcao-streamlit", {
      image: ecs.ContainerImage.fromRegistry("public.ecr.aws/h9e1x4p1/mcao-streamlit:latest"),
      memoryLimitMiB: 3072,
      cpu: 1024,
      logging: ecs.LogDriver.awsLogs({ streamPrefix: "mcao" }),
    });

    container.addPortMappings({
      containerPort: 8501,
    });

    const targetGroup = elbv2.ApplicationTargetGroup.fromTargetGroupAttributes(this, 'ImportedTargetGroup', {
      targetGroupArn: "arn:aws:elasticloadbalancing:us-east-1:500608964291:targetgroup/ecs-ganesh-mcao-service/728fdd3a220912ed",
    });

    // Import existing listener
    const listener = elbv2.ApplicationListener.fromApplicationListenerAttributes(this, "ExistingListener", {
      listenerArn: "arn:aws:elasticloadbalancing:region:account-id:listener/app/load-balancer-name/50dc6c495c0c9188/6f72db3c709f0c8f", // Replace with your Listener ARN
      securityGroup: securityGroup,
    });

    const fargateService = new ecs.FargateService(this, "ECSService", {
      cluster,
      taskDefinition,
      desiredCount: 1,
      serviceName: "mcao-service",
      securityGroups: [securityGroup],
      assignPublicIp: true,
      vpcSubnets: { subnets: subnets.subnets },
      healthCheckGracePeriod: cdk.Duration.seconds(60)
    });
    fargateService.attachToApplicationTargetGroup(targetGroup);

    new cdk.CfnOutput(this, "LoadBalancerDNS", {
      value: `http://mcao-lb-1093413639.us-east-1.elb.amazonaws.com:8501`,
      description: "DNS name of the load balancer",
    });

    // Output the name of the S3 bucket
    new cdk.CfnOutput(this, 'BucketName', {
      value: 'queryprostack-mybucketf68f3ff0-piigxfelaa5j',
    });
  }
}
