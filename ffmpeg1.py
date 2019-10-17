#!/usr/bin/env python3

import json
import logging
import sys
import os
from functools import wraps
from subprocess import PIPE, STDOUT, Popen, check_output
from datetime import datetime, timedelta
import time
import random
import plotly
from plotly import tools
import plotly.offline as pyo
import plotly.graph_objs as pygo

import boto3
import jwt
from flask import Flask, jsonify, make_response, redirect, request, url_for, render_template
from flask_login import login_user, current_user, login_required, logout_user, LoginManager, UserMixin

from authcheck import authenticate, get_user, get_uid, get_user_pwd
from form import DirForm, LoginForm


logging.basicConfig(level=logging.DEBUG)

login_manager = LoginManager()

app = Flask(__name__, template_folder='templates')
app.config['SECRET_KEY'] = 'shamkey'

login_manager.init_app(app)
login_manager.login_view = 'login'

secretkey = 'shamsecret'

ffprobe = '/usr/local/bin/ffprobe'
ffmpeg = '/usr/local/bin/ffmpeg'
lavfi = '-lavfi'
Filter = "-filter_complex"


class Meta():
    def __init__(self):
        pass

    def __call__(self, meta, bucket, asset):
        metadata = Popen([meta, '/mnt/' + bucket + '/' +
                          asset], stdout=PIPE, stderr=PIPE)
        self.stdout, self.stderr = metadata.communicate()
        self.returnValue = metadata.returncode
        if self.returnValue == 0:
            return self.stdout.decode('utf-8')
        else:
            return self.stderr

    def vmafRun(self, args, variant, refname):

        media_info = check_output(
            ['sudo', 'mediainfo', '--Output=JSON', '/mnt/' + args.get('variant_bucket') + variant])

        media_output = json.loads(media_info.decode('utf-8').replace("\n", ""))

        try:
            if media_output.get('media').get('track')[1].get('Height'):
                resolution = media_output.get('media').get('track')[
                    1].get('Height')
            else:
                resolution = media_output.get('media').get('track')[
                    1].get('Sampled_Height')
            bitrate = media_output.get('media').get('track')[1].get('BitRate')
            framerate = int(float(media_output.get(
                'media').get('track')[0].get('FrameRate')))
        except KeyError:
            print("Item Not Found")
        except Exception as err:
            print(str(err))

        if args.get('subsample'):
            if framerate == 23:
                gop = 48
            elif framerate == 29:
                gop = 60
            else:
                gop = 50

        ref_media_info = check_output(
            ['sudo', 'mediainfo', '--Output=JSON', '/mnt/' + args.get('reference_bucket') + args.get('reference_path')])

        ref_media_output = json.loads(
            ref_media_info.decode('utf-8').replace("\n", ""))

        try:
            if ref_media_output.get('media').get('track')[1].get('Height'):
                ref_resolution = ref_media_output.get('media').get('track')[
                    1].get('Height')
            else:
                ref_resolution = ref_media_output.get('media').get('track')[
                    1].get('Sampled_Height')
            ref_bitrate = ref_media_output.get('media').get('track')[
                1].get('BitRate')
        except KeyError:
            print("Item Not Found")
        except Exception as err:
            print(str(err))

        if ref_resolution == '2160' and resolution == '2160' and args.get('subsample'):
            arguments_n_s = 'libvmaf=model_path=/opt/vmaf/model/vmaf_4k_v0.6.1.pkl:n_subsample=' + \
                str(gop) + ':psnr=1:ssim=1:ms_ssim=1:log_fmt=json:log_path=/mnt/vmaf-scores/'
        elif ref_resolution == '2160' and resolution == '2160':
            arguments_n = 'libvmaf=model_path=/opt/vmaf/model/vmaf_4k_v0.6.1.pkl:psnr=1:ssim=1:ms_ssim=1:log_fmt=json:log_path=/mnt/vmaf-scores/'

        if ref_resolution == '2160' and args.get('subsample'):
            arguments_s = '[0:v]scale=3840x2160:flags=bicubic[main];[main][1:v]libvmaf=model_path=/home/ec2-user/vmaf/model/vmaf_4k_v0.6.1.pkl:n_subsample=' + \
                str(gop) + ':psnr=1:ssim=1:ms_ssim=1:log_fmt=json:log_path=/mnt/vmaf-scores/'
        elif ref_resolution != '2160' and args.get('subsample'):
            arguments_s = '[0:v]scale=3840x2160:flags=bicubic[main];[main][1:v]libvmaf=model_path=/home/ec2-user/vmaf/model/vmaf_v0.6.1.pkl:n_subsample=' + \
                str(gop) + ':psnr=1:ssim=1:ms_ssim=1:log_fmt=json:log_path=/mnt/vmaf-scores/'
        elif ref_resolution == '2160':
            arguments = '[0:v]scale=3840x2160:flags=bicubic[main];[main][1:v]libvmaf=model_path=/home/ec2-user/vmaf/model/vmaf_4k_v0.6.1.pkl:psnr=1:ssim=1:ms_ssim=1:log_fmt=json:log_path=/mnt/vmaf-scores/'
        elif ref_resolution != '2160':
            arguments = '[0:v]scale=3840x2160:flags=bicubic[main];[main][1:v]libvmaf=model_path=/home/ec2-user/vmaf/model/vmaf_v0.6.1.pkl:psnr=1:ssim=1:ms_ssim=1:log_fmt=json:log_path=/mnt/vmaf-scores/'

        print("REFERENCE-RESOLUTION:" + ref_resolution)
        print("RESOLUTION:" + resolution)
        print("REFERENCE-BITRATE:" + ref_bitrate)
        print("BITRATE:" + bitrate)

        requestTime = str(datetime.now()).replace(' ', '_').split(
            ':')[0] + ':' + str(datetime.now()).replace(' ', '_').split(':')[1]
        requestTime = requestTime.replace(':', '-')
        if args.get('username'):
            jsonfile = variant.split(
                '.')[0].split('/')[-1] + '__' + args.get('username') + '_' + requestTime + '_' + str(resolution) + '_' + str(bitrate)  # +  '.json'
        else:
            jsonfile = variant.split(
                '.')[0].split('/')[-1] + '__' + requestTime + '_' + str(resolution) + '_' + str(bitrate)  # + '.json'

        # Temp Only For Testing, as I am using the same file for variants!
        jsonfile = jsonfile + '_' + str(random.randint(1, 999)) + '.json'

        dirname = refname + '_' + requestTime

        dircreate = check_output(
            ['sudo', 'mkdir', '-p', '/mnt/vmaf-scores/' + dirname])
        dirpath = dirname + '/'

        out = open('/home/outputs/' + requestTime + '_stdout' +
                   '_' + str(resolution) + '_' + str(bitrate), 'w')
        err = open('/home/outputs/' + requestTime + '_stderr' +
                   '_' + str(resolution) + '_' + str(bitrate), 'w')

        timetorun = str(timedelta(seconds=int(args.get('timetorun'))))

        try:
            if args.get('timetorun') and args.get('subsample') and ref_resolution == '2160' and resolution == '2160':
                vmafscore = Popen(['sudo', ffmpeg, '-i', '/mnt/' + args.get('variant_bucket') + variant, '-i', '/mnt/' + args.get('reference_bucket') + args.get('reference_path'),
                                   lavfi, arguments_n_s + dirpath + jsonfile, '-t', timetorun, '-f', 'null', '-'], stdout=out, stderr=err)

            elif args.get('timetorun') and ref_resolution == '2160' and resolution == '2160':
                vmafscore = Popen(['sudo', ffmpeg, '-i', '/mnt/' + args.get('variant_bucket') + variant, '-i', '/mnt/' + args.get('reference_bucket') + args.get('reference_path'),
                                   lavfi, arguments_n + dirpath + jsonfile, '-t', timetorun, '-f', 'null', '-'], stdout=out, stderr=err)

            elif args.get('subsample') and ref_resolution == '2160' and resolution == '2160':
                vmafscore = Popen(['sudo', ffmpeg, '-i', '/mnt/' + args.get('variant_bucket') + variant, '-i', '/mnt/' + args.get('reference_bucket') + args.get('reference_path'),
                                   lavfi, arguments_n_s + dirpath + jsonfile, '-f', 'null', '-'], stdout=out, stderr=err)

            elif ref_resolution == '2160' and resolution == '2160':
                vmafscore = Popen(['sudo', ffmpeg, '-i', '/mnt/' + args.get('variant_bucket') + variant, '-i', '/mnt/' + args.get('reference_bucket') + args.get('reference_path'),
                                   lavfi, arguments_n + dirpath + jsonfile, '-f', 'null', '-'], stdout=out, stderr=err)

            elif args.get('timetorun') and args.get('subsample') and ref_resolution == '2160':
                vmafscore = Popen(['sudo', ffmpeg, '-i', '/mnt/' + args.get('variant_bucket') + variant, '-i', '/mnt/' + args.get('reference_bucket') + args.get('reference_path'),
                                   Filter, arguments_s + dirpath + jsonfile, '-t', timetorun, '-f', 'null', '-'], stdout=out, stderr=err)

            elif args.get('timetorun') and ref_resolution == '2160':
                vmafscore = Popen(['sudo', ffmpeg, '-i', '/mnt/' + args.get('variant_bucket') + variant, '-i', '/mnt/' + args.get('reference_bucket') + args.get('reference_path'),
                                   Filter, arguments + dirpath + jsonfile, '-t', timetorun, '-f', 'null', '-'], stdout=out, stderr=err)

            elif args.get('subsample') and ref_resolution == '2160':
                vmafscore = Popen(['sudo', ffmpeg, '-i', '/mnt/' + args.get('variant_bucket') + variant, '-i', '/mnt/' + args.get('reference_bucket') + args.get('reference_path'),
                                   Filter, arguments_s + dirpath + jsonfile, '-f', 'null', '-'], stdout=out, stderr=err)

            elif ref_resolution == '2160':
                vmafscore = Popen(['sudo', ffmpeg, '-i', '/mnt/' + args.get('variant_bucket') + variant, '-i', '/mnt/' + args.get('reference_bucket') + args.get('reference_path'),
                                   Filter, arguments + dirpath + jsonfile, '-f', 'null', '-'], stdout=out, stderr=err)

            time.sleep(5)
            return dirname if vmafscore.poll() is None else 1

        except Exception as err:
            print(str(err))
            return str(err)


class User(UserMixin):
    def __init__(self, user_name):
        self.user_name = user_name

    def get_id(self):
        object_id = get_uid(self.user_name)
        return str(object_id)


@login_manager.user_loader
def load_user(user_id):
    getuser = LoginForm()
    user_name = get_user_pwd(getuser.username.data)
    return User(user_name)


def auth_required(f):
    @wraps(f)
    def decorate(*args, **kwargs):
        if not request.headers.get('Authorization'):
            return redirect(url_for('index'))
        token = request.headers.get('Authorization')
        decoded = jwt.decode(token, secretkey, leeway=timedelta(seconds=10))
        if decoded.get('exp') > int(time.time()):
            return f(*args, **kwargs)
        return "Token Has Expired"
    return decorate


@app.route('/auth', methods=['POST'])
def get_token():
    content = request.get_json()
    (uname, pwd) = content.get('username'), content.get('password')
    if (uname, pwd) == authenticate(uname, pwd):
        token = jwt.encode({'exp': datetime.utcnow() +
                            timedelta(seconds=3600)}, secretkey)
        return token
    return "Invalid Username Or Password"


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:  # Added
        return redirect(url_for('plotdata'))
    form = LoginForm()
    if form.validate_on_submit():
        valid_user = get_user(form.username.data)
        if valid_user:
            (uname, pwd) = form.username.data, form.Password.data
            if (uname, pwd) == authenticate(uname, pwd):
                loginuser = User(uname)
                login_user(loginuser, remember=form.remember.data)  # Added
                next_page = request.args.get('next')
                # Check the next_page url hostname and port are empty.
                if not next_page:
                    next_page = url_for('list')
                return redirect(next_page)
            else:
                return '''<html><body><h1>Invalid Password</h1></body></html>'''
        else:
            return '''<html><body><h1>User Not Found, Please Get Your Creds From Admin</h1></body></html>'''
    return render_template('login.html', form=form)


@app.route('/')
@app.route('/post_info', methods=['GET'])
def index():
    return '''<html><body>Please Authenticate, Make A Json Post Request in {"Username": "yourusername", "password": "yourpassword"} format to /auth endpoint in order to get a JWT Token</body></html>'''


@app.route('/vmaf1', methods=['POST', 'GET'])
@auth_required
def vmaf1():
    '''Try to Fetch Data from Json Post, if not Data Posted Via Json, Fetch Parameters from the URI'''
    if request.method == 'GET':
        return jsonify({"---Request----": "---Format---",
                        "username (cbs Id <Optional>)": "syavagal",
                        "variant_bucket": "bucket_name",
                        "variant_path": "/dir1/variant1",
                        "reference_bucket": "bucket_name",
                        "reference_path": "/dir1/reference_path",
                        "timetorun (Seconds <Optional>)": "10",
                        "subsample (Frames <Optional>)": "10"})
    if request.is_json:
        content = request.get_json()

        if not content.get('variant_path') is not list:
            content['variant_path'] = content['variant_path'].split()

        for each in content.get('variant_path'):
            if not each.startswith("/"):
                each = '/' + each

        if not content["reference_path"].startswith("/"):
            content["reference_path"] = '/' + content["reference_path"]

        ref_name = content.get("reference_path").split('/')[-1].split('.')[0]

        for variant in content.get('variant_path'):
            data = Meta().vmafRun(content, variant, ref_name)

        if data == 1:
            return "Running vmaf on the asset failed", 500
        return f"Vmaf Submit Successful, Scores Will Be Emailed To You, if Provided Cbs Username In Post, Once you receive a completion email, You can make a request to '/plot' endpoint with '{str(data)}' as directory_name in Json Format i.e. dir:directory_name or pass as a Url parameter from your browser to see the plot of different bitrates, If you haven't provided your Cbs ID in the Request then you can manually check the Json File for Scores within the vmaf-scores S3 Bucket"
        # return str(data)


@app.route('/list', methods=['GET'])
def list():
    s3 = boto3.resource('s3', region_name='us-east-1')
    bucket = s3.Bucket(name='vmaf-scores')
    filelist = []
    for each in bucket.objects.all():
        if each.key[-1] == '/':
            filelist.append(each.key)
    return render_template('list.html', filelist=filelist)


@app.route('/plot', methods=['GET', 'POST'])
def plotdata():
    form = DirForm()
    if request.method == 'GET':
        return render_template('plot.html', form=form)
    try:
        vmafdir = request.args.get('dir') if request.args.get(
            'dir') else form.Dir.data
        if not os.path.isdir('/tmp/' + vmafdir):
            os.makedirs(os.path.join('/tmp', vmafdir))

        s3 = boto3.resource('s3', region_name='us-east-1')
        bucket = s3.Bucket(name='vmaf-scores')
        filelist = []
        for each in bucket.objects.all():
            if each.key.startswith(vmafdir):
                if each.key[-1] != '/':
                    filelist.append(each.key)

        for each in filelist:
            s3.Bucket('vmaf-scores').download_file(each, '/tmp/' +
                                                   vmafdir + '/' + each.split('/')[1])
    except Exception as e:
        return str(e)

    scores = {}
    framenums = {}
    for each in os.listdir('/tmp/' + vmafdir):
        with open('/tmp/' + vmafdir + '/' + each) as jsonfile:
            data = json.load(jsonfile)
            for frame in data.get('frames'):
                scores.setdefault(each, []).append(
                    frame.get('metrics').get('vmaf'))
                framenums.setdefault(each, []).append(
                    frame.get('frameNum'))

    for key, value in framenums.items():
        gop = True if value[1] != value[0] + 1 else False

    asset_title = vmafdir.split('_')[:1]

    framelist = [framenums_value for framenums_key,
                 framenums_value in framenums.items()]

    tracelist = []
    for title, score in scores.items():
        bitrate = title.split('__')[1].split('_')[4] + '_' + 'Bps'
        # trc = pygo.Scatter(x=list(range(1, len(score)+1)),
        trc = pygo.Scatter(x=framelist[0],
                           y=score, mode='lines', name=title.split('_')[0] + '_' + bitrate)
        tracelist.append(trc)

    ###
    layout = pygo.Layout(title=f"PLOTTING FOR * {asset_title[0]} * VARIANTS")

    ###
    figure = pygo.Figure(data=tracelist, layout=layout)

    ###
    figure.update_xaxes(title_text="Frame Number", showgrid=False)
    figure.update_yaxes(title_text="Vmaf Score", showgrid=False)

    jsongraph = json.dumps(figure, cls=plotly.utils.PlotlyJSONEncoder)

    return render_template('graph.html', jsongraph=jsongraph, gop=gop)


@app.route('/meta', methods=['POST', 'GET'])
@auth_required
def meta():
    if request.method == 'GET':
        return '''<html><body>Make A Json Post Request in {"meta": "ffprobe Or mediainfo", "bucket": "bucket_name", "asset":'asset_name'} format"</body></html>'''
    if request.is_json:
        content = request.get_json()
        bucket = content.get('bucket')
        meta = content.get('meta')
        if meta == 'ffprobe':
            meta = ffprobe
        asset = content.get('asset')
        metadata = Meta()
        return metadata(meta, bucket, asset)
    return "Request Should be Made in Json Format With bucket, asset and meta Values (meta = ffprobe/mediainfo)"


if __name__ == '__main__':
    app.run(debug=True, port=8080, host='0.0.0.0')
