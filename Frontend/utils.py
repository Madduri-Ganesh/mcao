import boto3
import streamlit as st
import botocore
import os 

# Add the case s3 Bucket
BUCKET_NAME = 'police-reports-pdf'

# Create an S3 client
s3_client = boto3.client("s3")

# Function to fetch the PDF from S3
@st.cache_data()
def fetch_pdf(case_name):
    key = f"{case_name}.pdf"
    print("Case Key : ",key)
    try:
        print("try")
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=key)
        pdf_bytes = response["Body"].read()
        return pdf_bytes
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == "404":
            print(f"The object {case_name} does not exist in bucket {BUCKET_NAME}")
        else:
            raise e