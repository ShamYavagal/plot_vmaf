#ShamYavagal

import os
import json
import boto3
import datetime
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

access_key = os.environ['ACCESS_KEY']
secret_key = os.environ['SECRET_KEY']
accesskey = os.environ['accesskey']
secretkey = os.environ['secretkey']

session = boto3.Session(aws_access_key_id=accesskey, aws_secret_access_key=secretkey)
s3 = session.resource('s3')
bucket = s3.Bucket('vmaf-scores')

def handler(event, context):
    try:
        try:
            event = event["detail"]
        except KeyError:
            print("KeyError")
        
        message1 = json.dumps(event, indent=4, sort_keys=True).replace(' ', '&nbsp;').replace('\n', '<br>')
        
        jsonfilekey = event.get('Records')[0].get('s3').get('object').get('key')
        print(jsonfilekey)
        
        jsondst = jsonfilekey.split('/')[-1]
        jsondir = jsonfilekey.split('/')[-2]
        print(jsondst)
        
        bucket.download_file(jsonfilekey, '/tmp/' + jsondst)
        print(os.listdir('/tmp'))
        
        
        vmaf_json = {}
        
        try:
            for line in reversed(list(open("/tmp/" + jsondst))):
                if "SSIM score" in line:
                    key = line.split(':')[0].strip()
                    key.replace('"', '')
                    vmaf_json[key] = line.split(':')[1].strip()
                elif "PSNR score" in line:
                    key = line.split(':')[0].strip()
                    key.replace('"', '')
                    vmaf_json[key] = line.split(':')[1].strip()
                elif "VMAF score" in line:
                    key = line.split(':')[0].strip()
                    key.replace('"', '')
                    vmaf_json[key] = line.split(':')[1].strip()
        except Exception as e:
            vmaf_json["error"] = e
            
        if not vmaf_json:
            vmaf_json["Message"] = "Not Able to Fetch The Scores From The Json File...Please Log In To S3 And Check The Json File Within vmaf-scores Bucket."
                
        #message2 = "Below Are The VMAF Scores For The Asset You Requested: " + "<br><br>" + json.dumps(vmaf_json, indent=4, sort_keys=True).replace(' ', '&nbsp;').replace('\n', '<br>')
        header = """<table class="tftable" border="1">
                        <tbody>
                        <tr>
                        <th colspan="4">""" + "VMAF Run Complete On Asset, Below Are The Scores" + """</th>
                        </tr>"""
                        #<th colspan="4">""" + "VMAF Run Complete On Asset, " + jsondst +  " Directory Name: "  + jsondir + " Below Are The Scores" + """</th>
        
        for key, value in vmaf_json.items():
            header += """<tr><td colspan="1">""" + " " + key.replace('"', '') + ' --> ' + value.replace(',', '') + " " + """</td></tr>"""
                
        try:
            recps = [jsonfilekey.split('__')[1].split('_')[0] + '@cbs.com']
        except:
            recps = ['syavagal@cbs.com']

        def SendEmail(From, receipients, subject, body):
            try:
                mail = smtplib.SMTP('email-smtp.us-east-1.amazonaws.com', 587)
                context = ssl.create_default_context()
                mail.starttls(context=context)
                mail.login(access_key, secret_key)
                message = MIMEMultipart("alternative")
                message["Subject"] = subject
                message["From"] = From
                message["To"] = ', '.join(receipients)
                htmlmsg = MIMEText(body, "html")
                message.attach(htmlmsg)
                mail.sendmail(From, receipients, message.as_string())
                print("mail SENT")
            except Exception as e:
                print(e)
        
        SendEmail('vmafscores@shonoc.com', recps, 'Vmaf Score For Thr Asset You Requested', header)
    except Exception as e:
        print(e)

