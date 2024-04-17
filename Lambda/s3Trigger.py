import boto3
import json
import os

def text_extraction(bucket_name, document_key):
    sns_topic_arn = os.environ['SNS_TOPIC_ARN']
    role_arn = os.environ['TEXTRACT_ROLE_ARN']
    
    textract = boto3.client('textract', region_name='us-east-1')
    
    # Call Textract to process the document
    try:
        response = textract.start_document_text_detection(
                    DocumentLocation={
                        "S3Object": {"Bucket": bucket_name, "Name": document_key}
                    },
                     NotificationChannel={
                    "SNSTopicArn": sns_topic_arn,
                    "RoleArn": role_arn,
            },
        )

        
        job_id = response['JobId']
        print(f"Started Textract job with id: {job_id}")
    except:
            print("Couldn't detect text in %s.", document_key)
            raise
    
    
    
def handler(event, context):
   

    bucket_name = os.environ['BUCKET_NAME']
    print(json.dumps(event))
    
    print("**************************")
    print("\n")
    
    body_val = json.loads(event['Records'][0]['body'])
    print(json.dumps(body_val))
    
    print("**************************")
    print("\n")
    
    message_val = json.loads(body_val['Message'])
    print(json.dumps(message_val))
    
    print("**************************")
    print("\n")
    
    document_key = message_val['Records'][0]['s3']['object']['key']
   
    
    
    #text-extraction function 
    text_extraction(bucket_name, document_key)
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            
        })
    }