import boto3
import os
import json

bucket_name = os.environ['BUCKET_NAME']
textract = boto3.client('textract')
s3 = boto3.client('s3') 

def handle_with_llm_casenumber(query):
    
   
    client = boto3.client('sagemaker-runtime')
    
    # Retrieve the endpoint name from environment variables
    endpoint_name = os.environ['SAGEMAKER_ENDPOINT_NAME']
    data = f"Your job is write the given data in nice detailed paragraphs. Keep the size same or more than the query size'{query}'"
 
    # Assuming 'data' is your input payload to the model

    payload = json.dumps({'inputs': data,
                          "parameters": {"max_new_tokens": 4000, "do_sample": False, "temperature": 0.3}
                          })

    # Send the query to the SageMaker endpoint
    
    response = client.invoke_endpoint(EndpointName=endpoint_name,
                                        ContentType='application/json',
                                        Body=payload)
    result = json.loads(response['Body'].read().decode('utf-8'))
    
    return result
    
    
    # bedrock = boto3.client(service_name='bedrock-runtime')
    # #MISTRAL MODEL PROMPT
    # prompt = "nSystem: Your job is to answer the asked questions using the provided data in a single word.\n\n\nHuman:"+query+ "\n\nAssistant:"
    # #prompt = "nSystem: Your job is to provide data, fields required to answer the questions in future.While providing the data, give me the question and then answer it\n\n\nHuman:"+query+ "\n\nAssistant:"

    # body = json.dumps({
    #     "prompt": prompt,
    #     "max_tokens":600,
    #     "temperature": 0.3
    # })

    # modelId = 'mistral.mixtral-8x7b-instruct-v0:1'
    # accept = 'application/json'
    # contentType = 'application/json'
    
    # response = bedrock.invoke_model(body=body, modelId=modelId, accept=accept, contentType=contentType)
    
    # response_body = json.loads(response.get('body').read())
    # return response_body
    

def save_case_number_to_dynamodb(extracted_data, document_url,bucket_name, document_key, table_name="caseDetailsTableV2"):
    #prompt1 = """Please answer the following questions in one word based on the provided data:1. Give me the case number or any unique identifier or a report number for this case which is mentioned in the provided data."""
        
    # model_input1 = f"{extracted_data}"
    # response1 = handle_with_llm_casenumber(model_input1)
    # print(response1)
    #case_number= response1["outputs"][0]["text"].strip()
    
    #storing the extracted data into S3 bucket
    s3_bucket_name = bucket_name  # Replace with your actual bucket name
    
    # Initialize the S3 client
    s3 = boto3.client('s3')
    
    # Define the S3 key for the extracted data file
    #s3_key_extracted_data = f"{case_number}.txt"
    
    s3_key_extracted_data = f"extracted/{document_key}.txt"
    # Convert extracted_data dictionary to a JSON string and then to bytes
    
    json_string = json.dumps(extracted_data, indent=2)

    # Clean the JSON string by removing slashes and replacing escape sequences
    clean_text = json_string.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\').replace('/', '')  # Removing slashes
    
    # Further clean text by removing other potential noise characters
    # For example, removing curly braces, square brackets, or unwanted punctuation
    # You can add or remove characters in the translate method as needed
    clean_text = clean_text.translate(str.maketrans('', '', '{}[]()<>'))
    
    # Encode the cleaned text string to bytes
    extracted_data_bytes = clean_text.encode('utf-8')
   # extracted_data_llm=handle_with_llm_casenumber(extracted_data_bytes)
   
    # Encode the cleaned text string to bytes
    
    try:
        s3.put_object(Bucket=s3_bucket_name, Key=s3_key_extracted_data, Body=extracted_data_bytes)
        print(f"Saved extracted data to S3: s3://{s3_bucket_name}/{s3_key_extracted_data}")
    except Exception as e:
        print(f"Failed to save extracted data to S3: {str(e)}")
        raise
    
    # Construct the S3 URL for the extracted data file
    extracted_data_url = f"https://{s3_bucket_name}.s3.amazonaws.com/{s3_key_extracted_data}"
    
    
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)
    # Save the case number, document URL, and extracted data URL to DynamoDB
    try:
        response = table.put_item(
            Item={
                'CaseNumber': document_key,
                'DocumentURL': document_url,
                'ExtractedDataURL': extracted_data_url
            }
        )
        print(f"Saved to DynamoDB: CaseNumber={document_key}, DocumentURL={document_url}, ExtractedDataURL={extracted_data_url}")
    except Exception as e:
        print(f"Failed to save to DynamoDB: {str(e)}")
        raise



def handler(event, context):

    body_val = json.loads(event['Records'][0]['body'])
    print(json.dumps(body_val))
    
    
    print("\n")
    
    message_val = json.loads(body_val['Message'])
    print(json.dumps(message_val))
    
    print("**************************")
    print("\n")
    
    job_id = message_val['JobId']
    print(job_id)
    
    object_name_value = message_val['DocumentLocation']['S3ObjectName']
    object_name_key = object_name_value.split(".", 1)
    
    key_val = object_name_key[0]
    
    print(json.dumps(key_val))
    
    print("********  BLOCKS METHOD RETURN  ***********")
    print("\n")
    
    
    
    blocks = get_all_blocks(job_id)
    print(blocks)
    
    print("**************************")
    print("\n")
    
    
    
    # print("**************************")
    # print("\n")
    document_url = f"https://s3.amazonaws.com/{bucket_name}/{key_val}"
    save_case_number_to_dynamodb(blocks, document_url, bucket_name, key_val)
    print("Created a file")
    
    return "Success"


def get_all_blocks(job_id):
    text = ""
    next_token = None
    finished = False
    lines=[]
    while not finished:
        # Get the job results
        if next_token:
            response = textract.get_document_text_detection(JobId=job_id, NextToken=next_token)
        else:
            response = textract.get_document_text_detection(JobId=job_id)
        # Merge the blocks from the response into the merged dictionary
        for item in response['Blocks']:
            if item['BlockType'] == 'LINE':
                #text += item['Text'] + " " + "\n"
                lines.append(item['Text'])

        # Check if there are more token responses
        if 'NextToken' in response:
            next_token = response['NextToken']
        else:
            finished = True
    return json.dumps({"text_lines": lines})    
    