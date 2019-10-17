from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField  #Added BooleanField
from wtforms.validators import DataRequired
from wtforms import ValidationError
from flask_login import UserMixin #Added


class DirForm(FlaskForm):
    Dir = StringField('Vmaf Json S3 Directory', validators=[DataRequired()])
    submit = SubmitField('Submit')

#-----------------------------------------------------------------------------------------------------

class LoginForm(FlaskForm, UserMixin):
    username = StringField('Username', validators=[DataRequired()])
    Password = PasswordField('Password', validators=[DataRequired()])
    login = SubmitField('Login')
    remember = BooleanField('Remember Me')