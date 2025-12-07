from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, SubmitField, SelectField,
    FloatField, IntegerField, FileField, TextAreaField
)
from wtforms.validators import DataRequired, Email, Length, EqualTo

# -----------------------
# Auth Forms
# -----------------------
class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')


class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=150)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    password_confirm = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

# -----------------------
# Prediction Forms
# -----------------------
class DiseaseForm(FlaskForm):
    image = FileField('Upload Crop Image', validators=[DataRequired()])
    submit = SubmitField('Predict Disease')


class RecommendForm(FlaskForm):
    N = FloatField('Nitrogen (N)', validators=[DataRequired()])
    P = FloatField('Phosphorus (P)', validators=[DataRequired()])
    K = FloatField('Potassium (K)', validators=[DataRequired()])
    temp = FloatField('Temperature (°C)', validators=[DataRequired()])
    humidity = FloatField('Humidity (%)', validators=[DataRequired()])
    ph = FloatField('pH Level', validators=[DataRequired()])
    rainfall = FloatField('Rainfall (mm)', validators=[DataRequired()])
    submit = SubmitField('Get Recommendation')


class YieldForm(FlaskForm):
    state = SelectField(
        'State',
        choices=[
            ('Andaman and Nicobar Islands', 'Andaman and Nicobar Islands'),
            ('Andhra Pradesh', 'Andhra Pradesh'),
            ('Arunachal Pradesh', 'Arunachal Pradesh'),
            ('Assam', 'Assam'),
            ('Bihar', 'Bihar'),
            ('Chandigarh', 'Chandigarh'),
            ('Chhattisgarh', 'Chhattisgarh')
        ]
    )
    district = SelectField(
        'District',
        choices=[
            ('NICOBARS', 'NICOBARS'),
            ('NORTH AND MIDDLE ANDAMAN', 'NORTH AND MIDDLE ANDAMAN'),
            ('SOUTH ANDAMANS', 'SOUTH ANDAMANS'),
            ('ANANTAPUR', 'ANANTAPUR'),
            ('CHITTOOR', 'CHITTOOR'),
            ('EAST GODAVARI', 'EAST GODAVARI'),
            ('GUNTUR', 'GUNTUR')
        ]
    )
    crop_year = IntegerField('Crop Year', validators=[DataRequired()])
    season = SelectField('Season', choices=[('Kharif', 'Kharif'), ('Whole Year', 'Whole Year'), ('Autumn', 'Autumn'), ('Rabi', 'Rabi'), ('Summer', 'Summer'), ('Winter', 'Winter')])
    crop = SelectField('Crop', choices=[
        ('Arecanut', 'Arecanut'),
        ('Other Kharif pulses', 'Other Kharif pulses'),
        ('Rice', 'Rice'),
        ('Banana', 'Banana'),
        ('Cashewnut', 'Cashewnut'),
        ('Coconut', 'Coconut'),
        ('Dry ginger', 'Dry ginger'),
        ('Sugarcane', 'Sugarcane'),
        ('Sweet potato', 'Sweet potato'),
        ('Tapioca', 'Tapioca')
    ])
    area = FloatField('Area (sq m)', validators=[DataRequired()])
    submit = SubmitField('Predict Yield')


class PriceForm(FlaskForm):
    state = SelectField('State', choices=[
        ('Andaman and Nicobar', 'Andaman and Nicobar'),
        ('Andhra Pradesh', 'Andhra Pradesh'),
        ('Assam', 'Assam'),
        ('Chattisgarh', 'Chattisgarh'),
        ('Goa', 'Goa'),
        ('Gujarat', 'Gujarat'),
        ('Haryana', 'Haryana'),
        ('Himachal Pradesh', 'Himachal Pradesh'),
        ('Jammu and Kashmir', 'Jammu and Kashmir'),
        ('Karnataka', 'Karnataka'),
        ('Kerala', 'Kerala'),
        ('Madhya Pradesh', 'Madhya Pradesh'),
        ('Maharashtra', 'Maharashtra'),
        ('Manipur', 'Manipur'),
        ('Meghalaya', 'Meghalaya'),
        ('Nagaland', 'Nagaland'),
        ('Odisha', 'Odisha'),
        ('Pondicherry', 'Pondicherry'),
        ('Punjab', 'Punjab'),
        ('Rajasthan', 'Rajasthan'),
        ('Tamil Nadu', 'Tamil Nadu'),
        ('Telangana', 'Telangana'),
        ('Tripura', 'Tripura'),
        ('Uttar Pradesh', 'Uttar Pradesh'),
        ('Uttrakhand', 'Uttrakhand'),
        ('West Bengal', 'West Bengal')
    ])
    district = SelectField('District', choices=[
        ('South Andaman', 'South Andaman'),
        ('Chittor', 'Chittor'),
        ('Kurnool', 'Kurnool'),
        ('West Godavari', 'West Godavari'),
        ('Cachar', 'Cachar'),
        ('Darrang', 'Darrang'),
        ('Dhubri', 'Dhubri'),
        ('Jorhat', 'Jorhat'),
        ('Kamrup', 'Kamrup'),
        ('Sonitpur', 'Sonitpur'),
        ('Bastar', 'Bastar'),
        ('Kanker', 'Kanker'),
        ('Surajpur', 'Surajpur'),
        ('North Goa', 'North Goa'),
        ('Amreli', 'Amreli'),
        ('Anand', 'Anand'),
        ('Bharuch', 'Bharuch'),
        ('Kachchh', 'Kachchh'),
        ('Kheda', 'Kheda'),
        ('Panchmahals', 'Panchmahals'),
        ('Surat', 'Surat'),
        ('Vadodara(Baroda)', 'Vadodara(Baroda)'),
        ('Valsad', 'Valsad')
    ])
    market = SelectField('Market', choices=[
        ('Port Blair', 'Port Blair'),
        ('Kalikiri', 'Kalikiri'),
        ('Mulakalacheruvu', 'Mulakalacheruvu'),
        ('Vayalapadu', 'Vayalapadu'),
        ('Banaganapalli', 'Banaganapalli'),
        ('Attili', 'Attili'),
        ('Cachar', 'Cachar'),
        ('Kharupetia', 'Kharupetia'),
        ('Gauripur', 'Gauripur'),
        ('Jorhat', 'Jorhat'),
        ('Pamohi(Garchuk)', 'Pamohi(Garchuk)'),
        ('Dhekiajuli', 'Dhekiajuli'),
        ('Jagdalpur', 'Jagdalpur')
    ])
    commodity = SelectField('Commodity', choices=[
        ('Amaranthus', 'Amaranthus'),
        ('Banana - Green', 'Banana - Green'),
        ('Bhindi(Ladies Finger)', 'Bhindi(Ladies Finger)'),
        ('Bitter gourd', 'Bitter gourd'),
        ('Black pepper', 'Black pepper'),
        ('Bottle gourd', 'Bottle gourd'),
        ('Brinjal', 'Brinjal'),
        ('Cabbage', 'Cabbage'),
        ('Carrot', 'Carrot'),
        ('Cauliflower', 'Cauliflower'),
        ('Cluster beans', 'Cluster beans'),
        ('Coconut', 'Coconut'),
        ('Colacasia', 'Colacasia'),
        ('Onion', 'Onion'),
        ('Potato', 'Potato'),
        ('Tomato', 'Tomato')
    ])
    variety = SelectField('Variety', choices=[
        ('Amaranthus', 'Amaranthus'),
        ('Banana - Green', 'Banana - Green'),
        ('Bhindi', 'Bhindi'),
        ('Other', 'Other'),
        ('Cluster Beans', 'Cluster Beans'),
        ('Big', 'Big'),
        ('Local', 'Local'),
        ('Desi (Whole)', 'Desi (Whole)'),
        ('Common', 'Common'),
        ('Fine', 'Fine')
    ])
    submit = SubmitField('Get Price')


class HealthForm(FlaskForm):
    insects_count = IntegerField('Estimated Insects Count per sq m', validators=[DataRequired()])
    crop_type = SelectField('Crop Type', choices=[('Food Crop', 'Food Crop'), ('Cash Crop', 'Cash Crop')])
    soil_type = SelectField('Soil Type', choices=[('Dry', 'Dry'), ('Wet', 'Wet')])
    pesticide_category = SelectField('Pesticide Use Category', choices=[
        ('Never', 'Never'),
        ('Previously Used', 'Previously Used'),
        ('Currently Using', 'Currently Using')
    ])
    doses_week = IntegerField('Number Doses per Week', validators=[DataRequired()])
    weeks_used = IntegerField('Number of Weeks Used', validators=[DataRequired()])
    weeks_quit = IntegerField('Number of Weeks Quit', validators=[DataRequired()])
    season = SelectField('Season', choices=[('Kharif', 'Kharif'), ('Rabi', 'Rabi'), ('Zaid', 'Zaid')])
    submit = SubmitField('Predict Health')


class FertilizerForm(FlaskForm):
    cropname = SelectField(
        'Crop Name',
        choices=[
            ('rice', 'Rice'),
            ('maize', 'Maize'),
            ('chickpea', 'Chickpea'),
            ('kidneybeans', 'Kidney Beans'),
            ('pigeonpeas', 'Pigeon Peas'),
            ('mothbeans', 'Moth Beans'),
            ('mungbean', 'Mung Bean'),
            ('blackgram', 'Black Gram'),
            ('lentil', 'Lentil'),
            ('pomegranate', 'Pomegranate'),
            ('banana', 'Banana'),
            ('mango', 'Mango'),
            ('grapes', 'Grapes'),
            ('watermelon', 'Watermelon'),
            ('muskmelon', 'Muskmelon'),
            ('apple', 'Apple'),
            ('orange', 'Orange'),
            ('papaya', 'Papaya'),
            ('coconut', 'Coconut'),
            ('cotton', 'Cotton'),
            ('jute', 'Jute'),
            ('coffee', 'Coffee')
        ],
        validators=[DataRequired()]
    )
    nitrogen = IntegerField('Nitrogen (N)', validators=[DataRequired()])
    phosphorous = IntegerField('Phosphorous (P)', validators=[DataRequired()])
    pottasium = IntegerField('Potassium (K)', validators=[DataRequired()])
    ph = FloatField('pH Value', validators=[DataRequired()])
    soil_moisture = IntegerField('Soil Moisture (%)', validators=[DataRequired()])
    submit = SubmitField('Get Recommendation')


class PostForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired()])
    description = TextAreaField('Description', validators=[DataRequired()])
    soil_nutrients = TextAreaField('Soil Nutrients (e.g., N:50, P:30)', validators=[DataRequired()])
    quality = StringField('Quality', validators=[DataRequired()])
    quantity = FloatField('Quantity', validators=[DataRequired()])
    rate = FloatField('Rate', validators=[DataRequired()])
    submit = SubmitField('Post Crop')


class ProductForm(FlaskForm):
    name = StringField('Product Name', validators=[DataRequired()])
    type = SelectField('Type', choices=[
        ('Seed', 'Seed'),
        ('Fertilizer', 'Fertilizer'),
        ('Pesticide', 'Pesticide'),
        ('Insecticide', 'Insecticide')
    ])
    description = TextAreaField('Description', validators=[DataRequired()])
    price = FloatField('Price', validators=[DataRequired()])
    quantity_available = IntegerField('Quantity Available', validators=[DataRequired()])
    submit = SubmitField('Post Product')


class MessageForm(FlaskForm):
    content = TextAreaField('Message', validators=[DataRequired()])
    submit = SubmitField('Send Message')


class PurchaseForm(FlaskForm):
    quantity = IntegerField('Quantity', validators=[DataRequired()])
    submit = SubmitField('Purchase')
