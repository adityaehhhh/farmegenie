import os
import pickle
import json
import base64
import numpy as np
import pandas as pd
import requests
from datetime import datetime
import tensorflow as tf
from tensorflow.keras.models import load_model
from PIL import Image, ImageOps
from flask import current_app
from flask_babel import gettext as _
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import io

MODEL_DIR = 'models'

# Load models at import time
model1 = pickle.load(open(os.path.join(MODEL_DIR, "Agri_pesticide.pkl"), "rb"))
model2 = pickle.load(open(os.path.join(MODEL_DIR, "Agri_pesticide.pkl"), "rb"))
model3 = pickle.load(open(os.path.join(MODEL_DIR, "Agri_pesticide.pkl"), "rb"))
model4 = pickle.load(open(os.path.join(MODEL_DIR, "cropRecommender.pkl"), "rb"))
model5 = load_model(os.path.join(MODEL_DIR, 'plant_disease.hdf5'))
model6 = pickle.load(open(os.path.join(MODEL_DIR, "Agri_pesticide.pkl"), "rb"))

# Functions to access config safely inside app context
def get_weather_api_key():
    return current_app.config['WEATHER_API_KEY']

def get_weather_base_url():
    return current_app.config['WEATHER_BASE_URL']

TRANSLATIONS = {
    'en': {
        'Alive': 'Alive',
        'Possible Damage due to other causes': 'Possible Damage due to other causes',
        'Damage due to Pesticides': 'Damage due to Pesticides',
        'Recommended Crop': 'Recommended Crop',
        'Estimated Yield': 'Estimated Yield',
        'Suggested Price': 'Suggested Price'
    },
    'hi': {
        'Alive': 'जिंदा',
        'Possible Damage due to other causes': 'अन्य कारणों से संभावित क्षति',
        'Damage due to Pesticides': 'कीटनाशकों के कारण क्षति',
        'Recommended Crop': 'अनुशंसित फसल',
        'Estimated Yield': 'अनुमानित उपज',
        'Suggested Price': 'सुझाया गया मूल्य'
    },
    'or': {
        'Alive': 'ଜୀବନ୍ତ',
        'Possible Damage due to other causes': 'ଅନ୍ୟ କାରଣରୁ ସମ୍ଭାବ କ୍ଷତି',
        'Damage due to Pesticides': 'କୀଟନାଶକ ଯୋଗୁଁ କ୍ଷତି',
        'Recommended Crop': 'ଅନୁସୁଚିତ ଫସଲ',
        'Estimated Yield': 'ଅନୁମାନିତ ଉତ୍ପାଦନ',
        'Suggested Price': 'ପ୍ରସ୍ତାବିତ ମୂଲ୍ୟ'
    },
    'pa': {
        'Alive': 'ਜੀਵੰਤ',
        'Possible Damage due to other causes': 'ਹੋਰ ਕਾਰਨਾਂ ਕਾਰਨ ਸੰਭਾਵਿਤ ਨੁਕਸਾਨ',
        'Damage due to Pesticides': 'ਕੀਟਨਾਸ਼ਕਾਂ ਕਾਰਨ ਨੁਕਸਾਨ',
        'Recommended Crop': 'ਸਿਫ਼ਾਰਸ਼ੀ ਫ਼ਸਲ',
        'Estimated Yield': 'ਅੰਦਾਜ਼ਨ ਉਪਜ',
        'Suggested Price': 'ਸੁਝਾਇਆ ਕੀਮਤ'
    }
}

def get_weather_data(city="Delhi"):
    try:
        api_key = get_weather_api_key()
        base_url = get_weather_base_url()
        url = f"{base_url}?q={city}&appid={api_key}&units=metric"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None

def get_weather_theme(weather_data):
    if not weather_data:
        return 'bright'
    weather_main = weather_data['weather'][0]['main'].lower()
    if 'rain' in weather_main or 'drizzle' in weather_main or 'thunderstorm' in weather_main:
        return 'stormy'
    return 'bright'

def translate_output(key):
    lang = current_app.config['BABEL_DEFAULT_LOCALE']  # Always accessed inside context
    return TRANSLATIONS.get(lang, TRANSLATIONS['en']).get(key, key)

def predict_crop_damage(inputs):
    prediction = model6.predict([[inputs['insects_count'], inputs['crop_type'], inputs['soil_type'],
                                  inputs['pesticide_category'], inputs['doses_week'], inputs['weeks_used'],
                                  inputs['weeks_quit'], inputs['season']]])
    result = int(prediction[0][0])
    if result == 0:
        return translate_output('Alive')
    elif result == 1:
        return translate_output('Possible Damage due to other causes')
    else:
        return translate_output('Damage due to Pesticides')

def import_and_predict(image_data, model):
    img = ImageOps.fit(image_data, size=(220, 220))
    x = tf.keras.preprocessing.image.img_to_array(img) / 255.0
    result = model.predict(np.expand_dims(x, axis=0))
    return result

def crop_recommendation(inputs):
    single_pred = np.array(list(inputs.values())).reshape(1, -1)
    prediction = model4.predict(single_pred)
    return f"{translate_output('Recommended Crop')}: {prediction[0].title()}"

def crop_price_prediction(inputs):
    ohe = pickle.load(open(os.path.join(MODEL_DIR, "ohe.pkl"), "rb"))
    model = load_model(os.path.join(MODEL_DIR, 'crop_price_prediction.h5'))
    input_array = np.array(list(inputs.values())).reshape(1, 5)
    encoded = ohe.transform(input_array)
    pred = model.predict(encoded)[0][0]
    return f"{translate_output('Suggested Price')}: ₹{pred:.2f} per quintal"

def yield_prediction(inputs):
    ohe = pickle.load(open(os.path.join(MODEL_DIR, "oneHotEncoder.pkl"), "rb"))
    model = pickle.load(open(os.path.join(MODEL_DIR, "classifier.pkl"), "rb"))
    encodings = pickle.load(open(os.path.join(MODEL_DIR, "list_mapping.pkl"), "rb"))
    df = pd.DataFrame([list(inputs.values())])
    onehot = ohe.transform(df[[0, 1]]).toarray()
    df_final = pd.concat([pd.DataFrame(onehot), df.drop([0, 1], axis=1)], axis=1)
    X = df_final.values
    X[0, 680] = encodings[0][int(X[0, 680])]
    X[0, 681] = encodings[1][int(X[0, 681])]
    pred = model.predict(X.reshape(1, -1))[0]
    return f"{translate_output('Estimated Yield')}: {pred:.2f} Kg per hectare"

def generate_pdf_report(predictions):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    story.append(Paragraph(_("Agri AI Prediction Report"), styles['Title']))
    data = [[_('Type'), _('Inputs'), _('Output'), _('Timestamp')]]
    for p in predictions:
        data.append([p.type, p.inputs[:50] + '...', p.output, p.timestamp.strftime('%Y-%m-%d %H:%M')])
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.green),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(table)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue() 