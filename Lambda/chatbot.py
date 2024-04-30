import boto3
import json
import os

def handler(event, context):
    print(event)  # Good for debugging
    query = event['question']  # Correctly extracts 'question', ensure your event uses 'question'
    
    parts = query.split()
    case_name = None  # Initialize case_name to None to avoid referenced before assignment error
    
    # for part in parts:
    #     if part.startswith('tempe'):
    #         suffix = part[5:]  # Extract everything after 'tempe'
    #         if suffix.isdigit():
    #             # If the suffix is all digits, we've found our case name
    #            case_name= part
    #            break
    if parts:
        # The last word in the query is the case name
        case_name = parts[-1]
    
    if not case_name:
        return {
            'statusCode': 400,
            'body': json.dumps({'message': event})
        }
    
    # S3 bucket details, ensure bucket name is correctly formatted and exists
    bucket_name = 'queryprostack-mybucketf68f3ff0-fb5h8ojyx7kj'
    file_key = f'extracted/{case_name}.txt'

    # Create an S3 client
    s3 = boto3.client('s3')

    # Try to download the text file from S3
    try:
        file_obj = s3.get_object(Bucket=bucket_name, Key=file_key)
        file_content = file_obj['Body'].read().decode('utf-8')
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'Failed to download the file from S3.', 'error': str(e)})
        }

    # Initialize the SageMaker runtime client
    client = boto3.client('sagemaker-runtime')

    endpoint_name = os.getenv('SAGEMAKER_ENDPOINT_NAME', 'jumpstart-dft-hf-llm-mixtral-8x7b-instruct-v2')
    combined_input = f"Answer this query precisely'{query}' using the extracted data: {file_content}. Give me answer in XML format"

    # Formatting the payload as expected
    payload = json.dumps({'inputs': combined_input,
                          "parameters": {"max_new_tokens": 600, "do_sample": False, "temperature": 0.3}
                          })

    # Send the query to the SageMaker endpoint
    try:
        response = client.invoke_endpoint(EndpointName=endpoint_name,
                                          ContentType='application/json',
                                          Body=payload)
        result = json.loads(response['Body'].read().decode('utf-8'))
        print("DEBUG: Result Structure:", result)  # Debugging line to inspect the structure
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'Failed to invoke SageMaker endpoint.', 'error': str(e)})
        }

    try:
        # Assuming 'result' should directly contain the 'generated_text' if it's not a list but a dictionary
        if isinstance(result, dict) and 'response' in result:
            generated_text = result['response'][0]['generated_text']
        elif isinstance(result, list):
            # Adjust this based on the actual structure you observe
            generated_text = result[0]['generated_text']
        else:
            raise ValueError("Unexpected result structure")
    except (KeyError, TypeError, IndexError, ValueError) as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'Error processing the SageMaker response.', 'error': str(e)})
        }

    return {
        'statusCode': 200,
        'body': json.dumps(generated_text)
    }
