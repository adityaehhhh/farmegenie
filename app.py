from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, session, g, current_app
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_babel import Babel, gettext as _
from flask_migrate import Migrate
from werkzeug.utils import secure_filename
import json
import io
import stripe
from config import Config, DevelopmentConfig
from models import db, User, Prediction, Role, CropPost, Product, Message, Purchase
from forms import *
from utils import *
import os
from forms import MessageForm
import openai
import requests
from nltk.stem import PorterStemmer
from nltk.tokenize import word_tokenize
import nltk

app = Flask(__name__)
app.config.from_object(DevelopmentConfig)
app.config.from_object('config.Config')
db.init_app(app)
migrate = Migrate(app, db)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

babel = Babel(app)

if app.config['STRIPE_SECRET_KEY']:
    stripe.api_key = app.config['STRIPE_SECRET_KEY']

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()

def get_locale():
    if request.args.get('lang'):
        session['lang'] = request.args.get('lang')
    return session.get(
        'lang',
        request.accept_languages.best_match(app.config['LANGUAGES']) or 'en'
    )

babel.init_app(app, locale_selector=get_locale)

@app.before_request
def before_request():
    g.locale = get_locale()

@app.route('/')
def index():
    weather_data = get_weather_data()
    theme = get_weather_theme(weather_data)
    return render_template('index.html', weather=weather_data, theme=theme)

@app.route('/set_language', methods=['POST'])
def set_language():
    lang = request.form.get('language')
    if lang in app.config['LANGUAGES']:
        session['lang'] = lang
    return redirect(request.referrer or url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash(_('Invalid email or password'))
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            flash(_('Email already registered'))
            return render_template('register.html', form=form)
        user = User(username=form.username.data, email=form.email.data)
        user.role = Role(request.form['role'])
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash(_('Registration successful! Please log in.'))
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    predictions = Prediction.query.filter_by(user_id=current_user.id).order_by(Prediction.timestamp.desc()).all()

    predictions_dict = []
    for pred in predictions:
        predictions_dict.append({
            'id': pred.id,
            'user_id': pred.user_id,
            'type': pred.type,
            'inputs': pred.inputs,
            'output': pred.output,
            'timestamp': pred.timestamp.strftime('%Y-%m-%d %H:%M:%S')  
        })

    return render_template('dashboard.html', predictions=predictions_dict)

@app.route('/report')
@login_required
def report():
    predictions = Prediction.query.filter_by(user_id=current_user.id).all()
    pdf = generate_pdf_report(predictions)
    return send_file(io.BytesIO(pdf), as_attachment=True, download_name='agri_ai_report.pdf', mimetype='application/pdf')

@app.route('/chatbot')
@login_required
def chatbot():
    theme = request.args.get('theme', 'bright')
    return render_template('bot.html', theme=theme)

try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

class ComprehensiveAgriChatbot:
    def __init__(self):
        self.stemmer = PorterStemmer()
        self.knowledge_base = self._initialize_knowledge_base()
    
    def _initialize_knowledge_base(self):
        """Initialize comprehensive agricultural knowledge base"""
        return {
            # Government Schemes
            'government_schemes': {
                'keywords': ['scheme', 'government', 'subsidy', 'yojana', 'sarkar', 'sarkari', 'benefit', 'apply'],
                'response': """🏛️ GOVERNMENT SCHEMES FOR FARMERS (2024-25):

**🌾 PM-KISAN SAMMAN NIDHI:**
• ₹6,000/year in 3 installments (₹2,000 each)
• Direct bank transfer every 4 months
• For small & marginal farmers (<2 hectares)
• Apply: pmkisan.gov.in
• Documents: Aadhaar, Bank Account, Land Records

**📱 DIGITAL AGRICULTURE MISSION (₹2,817 Crore):**
• Digital farming solutions
• AI-based crop advisory
• Weather-based alerts
• Market linkage platform

**🚜 PM-KUSUM (Solar Agriculture):**
• Solar pumps & grid-connected solar
• 30% subsidy + 30% loan + 40% farmer contribution
• Reduces electricity bills
• Environment-friendly farming

**🌱 PARAMPARAGAT KRISHI VIKAS YOJANA:**
• ₹50,000/hectare for organic farming
• 3-year certification support
• Premium prices for organic produce
• Soil health improvement

**💰 KISAN CREDIT CARD (KCC):**
• Crop loans at 4% interest
• ₹3 lakh limit without collateral
• Flexible repayment options
• Apply through banks/cooperatives

**🏥 AYUSHMAN BHARAT (Health Insurance):**
• ₹5 lakh family health cover
• Free treatment in empaneled hospitals
• No premium for farmers

Visit: agriwelfare.gov.in for complete details!"""
            },
            
            # Crop Insurance
            'crop_insurance': {
                'keywords': ['insurance', 'bima', 'pmfby', 'crop', 'loss', 'damage', 'compensation', 'claim'],
                'response': """🛡️ CROP INSURANCE - PMFBY (Pradhan Mantri Fasal Bima Yojana):

**📋 COVERAGE:**
• All notified crops in your area
• Natural calamities, pest attacks, diseases
• Individual farm-level coverage
• Pre-sowing to post-harvest losses

**💳 PREMIUM RATES:**
• Kharif: 2% of sum insured
• Rabi: 1.5% of sum insured
• Commercial/Horticultural: 5% of sum insured
• Government pays remaining 90%+ premium

**📊 SUM INSURED:**
• Based on average yield × MSP
• Or District Average Yield × Season Average Price
• Maximum coverage per hectare varies by crop

**📝 HOW TO APPLY:**
1. Visit nearest bank/insurance company
2. Submit: Aadhaar, Bank Account, Land Records
3. Pay premium within cutoff date
4. Get policy certificate

**⚡ CLAIM PROCESS:**
• Automatic for large-scale losses
• Individual losses: Report within 72 hours
• Assessment by government officials
• Direct bank transfer within 45 days

**📱 ONLINE SERVICES:**
• pmfby.gov.in - Check eligibility, apply
• Crop Insurance App
• Toll-free: 14447

**🎯 BENEFITS:**
• Financial protection against crop failures
• Encourages modern farming practices
• Access to credit becomes easier
• Peace of mind during farming"""
            },
            
            # Market Prices & Economics
            'market_prices': {
                'keywords': ['price', 'rate', 'mandi', 'market', 'sell', 'buy', 'profit', 'loss', 'msp', 'bhav'],
                'response': """📈 AGRICULTURAL MARKET INTELLIGENCE:

**🏪 MARKET PLATFORMS:**
• eNAM (National Agriculture Market) - enam.gov.in
• APMC Mandis - Real-time prices
• Farmer Producer Organizations (FPOs)
• Direct Marketing to retailers/consumers

**💰 MINIMUM SUPPORT PRICE (MSP) 2024-25:**
• Rice (Common): ₹2,320/quintal
• Wheat: ₹2,275/quintal
• Cotton: ₹6,620/quintal
• Sugarcane: ₹340/quintal
• Arhar (Tur): ₹7,000/quintal
• Gram (Chana): ₹5,440/quintal

**📱 PRICE CHECKING TOOLS:**
• AgriMarket app - Live mandi prices
• Kisan Suvidha app - Comprehensive farming info
• mKisan portal - SMS-based price alerts

**💡 SELLING STRATEGIES:**
• Avoid distress selling during harvest
• Use storage facilities (warehouses)
• Grade your produce properly
• Time your sales with market demand

**📊 VALUE ADDITION:**
• Food processing units
• Farmer Producer Companies
• Organic certification for premium prices
• Direct consumer sales through e-commerce

**🚛 LOGISTICS SUPPORT:**
• Kisan Rail - Discounted transport
• Kisan Udan - Air cargo for perishables
• Cold storage facilities
• FPO aggregation centers

Contact local APMC or visit agmarknet.gov.in for daily prices!"""
            },
            
            # Disease Management
            'disease_management': {
                'keywords': ['disease', 'fungus', 'bacteria', 'virus', 'infection', 'pest', 'insect', 'bug', 'damage', 'treatment', 'medicine'],
                'response': """🔬 COMPREHENSIVE DISEASE & PEST MANAGEMENT:

**🍄 FUNGAL DISEASES:**
• Blast, Blight, Rust, Smut, Wilt
• Treatment: Copper Oxychloride, Mancozeb, Propiconazole
• Organic: Neem oil, Trichoderma, Copper fungicides
• Prevention: Seed treatment, crop rotation

**🦠 BACTERIAL DISEASES:**
• Bacterial leaf blight, Soft rot, Fire blight
• Treatment: Streptocycin, Plantomycin, Copper compounds
• Biocontrol: Pseudomonas, Bacillus subtilis

**🐛 MAJOR PESTS:**
• Bollworm, Aphids, Thrips, Stem borer, Fruit fly
• Chemical: Chlorpyrifos, Imidacloprid, Cypermethrin
• Biological: Bt spray, Trichogramma, NPV
• Organic: Neem, Pongamia, Karanja oil

**🌱 INTEGRATED PEST MANAGEMENT (IPM):**
• Crop rotation & resistant varieties
• Biological control agents
• Pheromone traps & light traps
• Selective pesticide use
• Border crops & trap crops

**🔍 DISEASE IDENTIFICATION:**
• Leaf spots, yellowing, wilting symptoms
• Upload photos to our disease detection tool
• Contact nearest KVK (Krishi Vigyan Kendra)
• WhatsApp: 9876543210 (AgriExpert)

**💉 SPRAY SCHEDULE:**
• Preventive: 15-day intervals during vulnerable stages
• Curative: Immediate after symptom appearance
• Follow PHI (Pre-Harvest Interval)
• Use sticker & spreader for better coverage

**🌿 ORGANIC ALTERNATIVES:**
• Cow urine + neem leaf extract
• Ginger-garlic-chilli spray
• Buttermilk + turmeric spray
• Mahua oil emulsion

Remember: Always read pesticide labels and follow safety precautions!"""
            },
            
            # Fertilizers & Soil Management
            'fertilizer_soil': {
                'keywords': ['fertilizer', 'nutrient', 'nitrogen', 'phosphorus', 'potassium', 'npk', 'urea', 'dap', 'soil', 'ph', 'organic', 'compost'],
                'response': """🧪 SOIL HEALTH & FERTILIZER MANAGEMENT:

**📊 SOIL TESTING:**
• Get soil tested every 2-3 years
• Parameters: pH, EC, Organic Carbon, NPK, Micronutrients
• Cost: ₹100-200 per sample
• Contact: District Collector office, KVK, Soil Testing Labs

**⚖️ NPK MANAGEMENT:**
• **NITROGEN (N):** Urea (46%), Ammonium Sulphate (20.6%), CAN (25%)
• **PHOSPHORUS (P):** DAP (46%), SSP (16%), TSP (46%)
• **POTASSIUM (K):** MOP (60%), SOP (50%), Potash

**📏 FERTILIZER CALCULATION:**
• Rice: 120N:60P:40K kg/hectare
• Wheat: 120N:60P:40K kg/hectare
• Cotton: 150N:75P:75K kg/hectare
• Vegetables: 150-200N:100P:100K kg/hectare

**🌿 ORGANIC FERTILIZERS:**
• **FYM:** 8-10 tons/hectare (0.5N:0.3P:0.5K%)
• **Vermicompost:** 2-3 tons/hectare (1.5N:1P:1K%)
• **Green Manure:** Dhaincha, Sunhemp, Cowpea
• **Biofertilizers:** Rhizobium, Azotobacter, PSB, KSB

**🧬 MICRONUTRIENTS:**
• **Iron (Fe):** FeSO4 - For chlorosis, yellowing
• **Zinc (Zn):** ZnSO4 - 25 kg/hectare soil application
• **Boron (B):** Borax - For flower/fruit development
• **Manganese (Mn):** MnSO4 - Enzyme activation

**📈 SOIL pH MANAGEMENT:**
• **Acidic Soil (pH<5.5):** Apply lime 2-4 tons/hectare
• **Alkaline Soil (pH>8.5):** Apply gypsum 2-5 tons/hectare
• **Saline Soil:** Gypsum + organic matter + drainage

**💧 FERTIGATION:**
• Water-soluble fertilizers through drip irrigation
• 20-30% fertilizer saving
• Better nutrient use efficiency
• Precise application timing

**🔄 APPLICATION TIMING:**
• **Basal:** 50% N + 100% P & K at sowing
• **Top Dressing:** Remaining N in 2-3 splits
• **Foliar Spray:** Micronutrients at critical stages

Use our Fertilizer Calculator tool for precise recommendations!"""
            },
            
            # Irrigation Systems
            'irrigation': {
                'keywords': ['water', 'irrigation', 'drip', 'sprinkler', 'flood', 'furrow', 'pump', 'bore', 'well', 'rain'],
                'response': """💧 MODERN IRRIGATION SYSTEMS & WATER MANAGEMENT:

**🌊 IRRIGATION METHODS:**

**💧 DRIP IRRIGATION:**
• 90% water use efficiency
• 30-40% water saving vs flood irrigation
• Reduces weed growth & soil erosion
• Cost: ₹1,50,000-2,00,000/hectare
• Subsidy: 50-90% under PMKSY

**☔ SPRINKLER IRRIGATION:**
• 75-80% water use efficiency
• Suitable for all soil types
• Covers large areas quickly
• Cost: ₹80,000-1,20,000/hectare
• Good for cereals, vegetables, orchards

**🌾 TRADITIONAL METHODS:**
• **Flood Irrigation:** 30-40% efficiency, suitable for rice
• **Furrow Irrigation:** 50-60% efficiency, for row crops
• **Basin Irrigation:** For fruit trees & perennials

**⚙️ IRRIGATION EQUIPMENT:**

**🚰 PUMPS:**
• **Electric Submersible:** 5-20 HP for bore wells
• **Solar Pumps:** Under PM-KUSUM, 90% subsidy
• **Diesel Pumps:** Portable, 5-10 HP
• **Centrifugal Pumps:** Surface water lifting

**🏗️ WATER SOURCES:**
• **Tube Wells/Bore Wells:** 100-300 feet depth
• **Dug Wells:** Traditional, 20-50 feet
• **Surface Water:** Rivers, canals, ponds
• **Rainwater Harvesting:** Storage tanks, check dams

**📊 WATER REQUIREMENT:**
• **Rice:** 1500-2000 mm/season
• **Wheat:** 450-600 mm/season
• **Cotton:** 700-1300 mm/season
• **Sugarcane:** 1500-2500 mm/season

**⏰ IRRIGATION SCHEDULING:**
• **Critical Stages:** Flowering, grain filling
• **Soil Moisture:** 50-80% field capacity
• **Tensiometer:** For precise measurement
• **Weather-based:** Avoid irrigation before rain

**💰 GOVERNMENT SCHEMES:**
• **PMKSY (Per Drop More Crop):** 55% subsidy
• **MGNREGA:** Pond/well construction
• **State Schemes:** Additional 20-30% subsidy

**🌱 WATER CONSERVATION:**
• **Mulching:** Reduces evaporation by 50%
• **Crop Residue:** Natural mulch material
• **Plastic Mulch:** For high-value crops
• **Intercropping:** Efficient water utilization

**📱 TECHNOLOGY:**
• **Soil Moisture Sensors:** IoT-based monitoring
• **Weather Stations:** Local weather data
• **Mobile Apps:** IrriGuru, CropIn, AquaCrop

Apply for irrigation subsidies at your nearest agriculture office!"""
            },
            
            # Crop Selection & Rotation
            'crop_selection': {
                'keywords': ['crop', 'variety', 'seed', 'rotation', 'intercrop', 'season', 'kharif', 'rabi', 'zaid', 'hybrid'],
                'response': """🌾 SMART CROP SELECTION & ROTATION STRATEGIES:

**🗓️ CROPPING SEASONS:**

**☔ KHARIF (June-November):**
• **Cereals:** Rice, Maize, Bajra, Jowar
• **Pulses:** Arhar, Moong, Urad, Cowpea
• **Cash Crops:** Cotton, Sugarcane, Groundnut
• **Vegetables:** Bottle gourd, Ridge gourd, Okra

**❄️ RABI (November-April):**
• **Cereals:** Wheat, Barley, Oats
• **Pulses:** Gram, Lentil, Pea, Mustard
• **Vegetables:** Potato, Onion, Garlic, Cabbage
• **Spices:** Coriander, Fenugreek, Cumin

**☀️ ZAID (April-June):**
• **Cereals:** Rice, Maize (irrigated)
• **Vegetables:** Cucumber, Watermelon, Muskmelon
• **Fodder:** Jowar, Bajra, Maize

**🔄 CROP ROTATION BENEFITS:**
• Soil fertility improvement
• Pest & disease control
• Weed management
• Risk diversification
• Sustainable income

**📋 ROTATION EXAMPLES:**
• **Rice-Wheat-Moong:** Traditional system
• **Cotton-Wheat-Fodder:** Semi-arid regions
• **Sugarcane-Wheat-Summer moong:** Irrigated areas
• **Groundnut-Mustard-Summer fodder:** Rainfed areas

**🌱 HIGH-YIELDING VARIETIES:**

**🌾 RICE:**
• **Basmati:** Pusa Basmati 1121, CSR 30
• **Non-Basmati:** Swarna, MTU 1010, BPT 5204
• **Hybrid:** CORH 2, DRRH 3, PHB 71

**🌾 WHEAT:**
• **Irrigated:** HD 2967, PBW 725, DBW 187
• **Rainfed:** Raj 4120, MP 3288, HI 1544
• **Durum:** HI 8713, PDW 314

**🧄 CASH CROPS:**
• **Cotton:** Bt Cotton - Bollgard II varieties
• **Sugarcane:** Co 0238, CoM 0265, Co 15023
• **Groundnut:** TG 37A, ICGV 91114, TAG 24

**🥬 INTERCROPPING SYSTEMS:**
• **Cotton + Arhar:** 4:2 ratio
• **Sugarcane + Potato:** Early potato harvest
• **Wheat + Mustard:** 6:2 ratio
• **Maize + Soybean:** 2:1 ratio

**📊 SELECTION CRITERIA:**
• **Climate:** Temperature, rainfall, humidity
• **Soil:** Type, pH, drainage, fertility
• **Market:** Demand, price trends, storage
• **Resources:** Water, labor, mechanization
• **Risk:** Disease resistance, weather tolerance

**🎯 EMERGING CROPS:**
• **Millets:** Finger millet, Pearl millet, Foxtail millet
• **Quinoa:** Super food with high protein
• **Chia Seeds:** Health food market
• **Dragon Fruit:** High-value horticulture

Use our Crop Recommendation tool for personalized suggestions!"""
            },
            
            # Organic Farming & Sustainability
            'organic_farming': {
                'keywords': ['organic', 'natural', 'bio', 'sustainable', 'chemical', 'pesticide', 'certification', 'compost'],
                'response': """🌿 ORGANIC & SUSTAINABLE FARMING GUIDE:

**🎯 ORGANIC FARMING PRINCIPLES:**
• No synthetic fertilizers or pesticides
• Soil health through organic matter
• Biodiversity conservation
• Natural pest management
• Sustainable resource use

**💚 ORGANIC INPUTS:**

**🌱 FERTILIZERS:**
• **Compost:** Kitchen waste, crop residue, animal dung
• **Vermicompost:** Earthworm castings (2-3 tons/hectare)
• **Green Manure:** Dhaincha, Sunhemp (40-50 days)
• **Biofertilizers:** Rhizobium, Azotobacter, PSB

**🪲 PEST MANAGEMENT:**
• **Neem Products:** Azadirachtin 10,000 ppm
• **Bt (Bacillus thuringiensis):** Biological pesticide
• **Trichoderma:** Fungal biocontrol agent
• **NPV (Nuclear Polyhedrosis Virus):** For caterpillars

**🏠 ON-FARM PREPARATIONS:**

**🍯 PANCHAGAVYA:**
• Cow dung (7 kg) + Cow urine (10 liters)
• Cow milk (3 liters) + Curd (2 liters)
• Cow ghee (1 liter) + Banana (12 pieces)
• Jaggery (3 kg) + Coconut water (3 liters)
• Ferment for 20 days, use 200ml/15 liters water

**🌶️ CHILLI-GARLIC SPRAY:**
• Green chilli (100g) + Garlic (50g)
• Grind, boil in 1 liter water
• Cool, filter, add soap (5ml)
• Spray in evening hours

**📜 CERTIFICATION PROCESS:**
• **Agencies:** APEDA, SGS, Control Union, OneCert
• **Inspection:** Annual farm visits
• **Documentation:** Input records, harvest data
• **Certification:** 18-24 months process
• **Cost:** ₹15,000-25,000 per year

**💰 FINANCIAL SUPPORT:**
• **PKVY:** ₹50,000/hectare for 3 years
• **Mission Organic Value Chain:** Cluster development
• **NCOF:** Technical support & training
• **Zero Budget Natural Farming:** State schemes

**📈 MARKET OPPORTUNITIES:**
• **Premium Price:** 20-30% above conventional
• **Export Markets:** USA, Europe, Japan
• **Domestic Demand:** Growing 25% annually
• **Direct Sales:** Farmers markets, online platforms

**🌾 CROP-SPECIFIC GUIDANCE:**

**🍅 VEGETABLES:**
• Use organic seeds & seedlings
• Companion planting (marigold, basil)
• Regular monitoring & handpicking
• Organic mulching

**🌾 CEREALS:**
• Select disease-resistant varieties
• Proper crop rotation
• Integrated nutrient management
• Biological pest control

**🍊 FRUITS:**
• Organic manures in fruit plants
• Beneficial insect conservation
• Minimal processing
• Proper post-harvest handling

Join organic farming groups for knowledge sharing and marketing support!"""
            },
            
            # Agricultural Mechanization
            'mechanization': {
                'keywords': ['machine', 'tractor', 'harvester', 'equipment', 'implement', 'technology', 'automation'],
                'response': """🚜 AGRICULTURAL MECHANIZATION & FARM EQUIPMENT:

**🚜 TRACTORS:**
• **30-40 HP:** Small farms, orchard operations
• **45-60 HP:** Medium farms, general purpose
• **60+ HP:** Large farms, heavy operations
• **Brands:** Mahindra, Sonalika, New Holland, John Deere

**🌾 HARVESTING EQUIPMENT:**
• **Combine Harvester:** ₹25-40 lakhs, 1000-2000 hectares/season
• **Paddy Transplanter:** ₹4-6 lakhs, 8-10 hectares/day
• **Reaper:** ₹3-5 lakhs, manual/self-propelled
• **Thresher:** ₹50,000-2 lakhs, stationary/mobile

**🌱 PLANTING EQUIPMENT:**
• **Seed Drill:** Precise seed placement
• **Multi-Crop Planter:** Versatile seeding
• **Zero Till Drill:** No-tillage farming
• **Transplanter:** For rice, vegetables

**💧 IRRIGATION EQUIPMENT:**
• **Drip Systems:** Netafim, Jain, Finolex
• **Sprinkler Systems:** Rain guns, center pivot
• **Solar Pumps:** 5-20 HP capacity
• **Water Pumps:** Submersible, centrifugal

**🚛 POST-HARVEST EQUIPMENT:**
• **Winnowing Fan:** Cleaning grains
• **Color Sorter:** Quality improvement
• **Storage Bins:** Scientific storage
• **Drying Systems:** Reduce moisture content

**💰 SUBSIDIES & FINANCING:**

**📋 SUB-MISSION ON AGRICULTURAL MECHANIZATION:**
• 50% subsidy on farm equipment
• Maximum ₹1.25 lakh subsidy per beneficiary
• Priority to SC/ST, small farmers, women

**🏦 CREDIT SCHEMES:**
• **Kisan Credit Card:** Equipment loans
• **NABARD Schemes:** Refinancing support
• **Manufacturer Finance:** 0-5% interest rates
• **Hire Purchase:** 20% down payment options

**🤝 CUSTOM HIRING CENTERS:**
• Rent equipment per hour/day/acre
• Village-level entrepreneurs
• Reduces individual investment
• Government support for establishment

**📱 PRECISION AGRICULTURE:**
• **GPS Guidance:** Auto-steering tractors
• **Variable Rate Technology:** Site-specific application
• **Drones:** Crop monitoring, spraying
• **IoT Sensors:** Real-time field monitoring

**🌾 CROP-SPECIFIC MECHANIZATION:**

**🌾 RICE:**
• Puddling → Transplanting → Harvesting → Threshing
• DSR (Direct Seeded Rice) equipment
• Straw management machines

**🌾 WHEAT:**
• Land preparation → Seeding → Harvesting → Threshing
• Happy seeder for residue management
• Combine harvester with straw chopper

**🥔 VEGETABLES:**
• Bed formers, mulch laying equipment
• Seedling transplanters
• Harvesting aids for root vegetables

**⚡ FARM POWER SOURCES:**
• **Human Power:** 30% of total farm operations
• **Animal Power:** Bullocks still used in 40% farms
• **Tractor Power:** 45% and increasing
• **Electric/Solar:** Growing adoption

**🔧 MAINTENANCE TIPS:**
• Regular servicing every 100-250 hours
• Genuine spare parts usage
• Proper storage during off-season
• Operator training programs

Contact your nearest FAME (Farm Mechanization) office for subsidies!"""
            },
            
            # Weather & Climate
            'weather_climate': {
                'keywords': ['weather', 'climate', 'rain', 'temperature', 'humidity', 'drought', 'flood', 'monsoon'],
                'response': """🌤️ WEATHER-BASED FARMING & CLIMATE RESILIENCE:

**☔ MONSOON PATTERNS:**
• **Southwest Monsoon:** June-September (75% rainfall)
• **Northeast Monsoon:** October-December (Tamil Nadu, Andhra)
• **Pre-monsoon:** April-May (Kerala, Karnataka)
• **Western Disturbances:** Winter rains (North India)

**🌡️ TEMPERATURE ZONES:**
• **Tropical:** >18°C, rice, cotton, sugarcane
• **Sub-tropical:** 12-18°C, wheat, barley, mustard
• **Temperate:** 5-12°C, apple, walnut, saffron
• **Alpine:** <5°C, limited agriculture

**💧 RAINFALL ZONES:**
• **High Rainfall (>200cm):** Rice, tea, rubber
• **Medium Rainfall (100-200cm):** Cotton, sugarcane
• **Low Rainfall (50-100cm):** Millets, pulses
• **Arid (<50cm):** Desert crops, drought-tolerant

**📱 WEATHER FORECASTING SERVICES:**
• **IMD:** India Meteorological Department
• **Agromet Advisory:** District-wise guidance
• **GKMS:** Gramin Krishi Mausam Seva
• **Mobile Apps:** Meghdoot, Damini, Mausam

**🌊 CLIMATE CHANGE ADAPTATION:**

**🌱 DROUGHT-RESISTANT CROPS:**
• **Millets:** Pearl millet, finger millet, sorghum
• **Pulses:** Cowpea, moth bean, cluster bean
• **Oilseeds:** Castor, safflower, niger
• **Varieties:** Drought-tolerant hybrid seeds

**🌊 FLOOD-RESISTANT VARIETIES:**
• **Rice:** Swarna Sub-1, Sambha Mahsuri Sub-1
• **Submergence tolerance:** 10-15 days underwater
• **Quick recovery:** After flood receding
• **Scuba rice:** International varieties

**❄️ COLD-TOLERANT CROPS:**
• **Vegetables:** Radish, carrot, spinach, peas
• **Cereals:** Winter wheat, barley
• **Protection:** Mulching, tunnel farming
• **Frost protection:** Smoke, irrigation, covers

**🔥 HEAT-TOLERANT VARIETIES:**
• **Wheat:** HD 3086, DBW 88, HD 2967
• **Rice:** N22, Nagina 22, Samba Mahsuri
• **Vegetables:** Heat-tolerant tomato, chilli
• **Management:** Shade nets, early planting

**💨 EXTREME WEATHER MANAGEMENT:**

**🌪️ CYCLONE PREPAREDNESS:**
• Early warning systems
• Crop insurance coverage
• Emergency harvesting plans
• Safe storage facilities

**⛈️ HAIL PROTECTION:**
• Anti-hail nets for orchards
• Weather-based insurance
• Crop diversification
• Flexible planting dates

**☀️ HEAT WAVE PROTECTION:**
• Irrigation scheduling
• Mulching practices
• Shade structures
• Heat-tolerant varieties

**📊 AGRO-CLIMATIC ZONES:**
• **Zone I:** Western Himalayas
• **Zone II:** Eastern Himalayas  
• **Zone III:** Lower Gangetic Plains
• **Zone IV:** Middle Gangetic Plains
• **Zone V:** Upper Gangetic Plains
• **Zone VI:** Trans-Gangetic Plains
• **Zone VII:** Eastern Plateau & Hills
• **Zone VIII:** Central Plateau & Hills
• **Zone IX:** Western Plateau & Hills
• **Zone X:** Southern Plateau & Hills
• **Zone XI:** East Coast Plains & Hills
• **Zone XII:** West Coast Plains & Ghats
• **Zone XIII:** Gujarat Plains & Hills
• **Zone XIV:** Western Dry Region
• **Zone XV:** The Islands

**🌾 SEASON-WISE ADVISORIES:**
• Crop selection based on weather forecast
• Pest outbreak predictions
• Irrigation planning
• Harvest timing optimization

Subscribe to Agromet Advisory (9915937030) for your district!"""
            },
            
            # Livestock Integration
            'livestock': {
                'keywords': ['cattle', 'dairy', 'cow', 'buffalo', 'goat', 'sheep', 'poultry', 'animal', 'milk', 'livestock'],
                'response': """🐄 INTEGRATED LIVESTOCK FARMING SYSTEMS:

**🐄 DAIRY FARMING:**

**🥛 DAIRY BREEDS:**
• **Indigenous:** Gir, Sahiwal, Red Sindhi, Tharparkar
• **Crossbred:** HF×Local, Jersey×Local
• **Buffalo:** Murrah, Mehsana, Surti, Jaffarabadi
• **Milk Yield:** 10-25 liters/day (high-yielding)

**🌾 CATTLE FEED:**
• **Green Fodder:** Hybrid Napier, Berseem, Lucerne
• **Dry Fodder:** Wheat/rice straw, hay
• **Concentrate:** Cattle feed (18-20% protein)
• **Minerals:** Salt, calcium, phosphorus supplements

**📊 MILK PRODUCTION ECONOMICS:**
• **Cost:** ₹25-30 per liter production cost
• **Selling Price:** ₹35-45 per liter
• **Profit:** ₹8-15 per liter
• **Break-even:** 2-3 animals minimum

**🐐 GOAT FARMING:**
• **Breeds:** Boer, Jamunapari, Barbari, Sirohi
• **Investment:** ₹50,000-1,00,000 for 10 goats
• **Returns:** ₹15,000-25,000/goat/year
• **Feed:** Grazing + 200-300g concentrate/day

**🐑 SHEEP FARMING:**
• **Wool Breeds:** Chokla, Nali, Marwari
• **Mutton Breeds:** Osmanabadi, Mandya, Hassan
• **Flock Size:** 50-100 animals optimal
• **Grazing System:** Extensive/semi-intensive

**🐓 POULTRY FARMING:**
• **Broiler:** 35-40 days cycle, 2-2.5 kg weight
• **Layer:** 300-320 eggs/year production
• **Country Chicken:** Higher price, slower growth
• **Investment:** ₹5-8 lakh for 1000 birds

**💰 GOVERNMENT SCHEMES:**
• **NABARD Subsidies:** 25-35% for dairy/poultry
• **Dairy Entrepreneurship Development:** IDDM scheme
• **Backyard Poultry:** ₹18,000 assistance for 20 birds
• **Goat Development:** State-specific schemes

**🏥 ANIMAL HEALTH:**
• **Vaccination Schedule:** FMD, HS, BQ vaccines
• **Deworming:** Every 3-4 months
• **Mineral Supplements:** Area-specific licks
• **AI Services:** Artificial insemination centers

**🌾 CROP-LIVESTOCK INTEGRATION:**
• **Crop Residue:** Fodder from wheat/rice straw
• **Organic Manure:** Animal waste for crops
• **Mixed Farming:** Diversified income sources
• **Grazing:** Stubble grazing after harvest

**🥛 VALUE ADDITION:**
• **Dairy Processing:** Cheese, butter, ghee
• **Meat Processing:** Value-added products
• **Organic Certification:** Premium prices
• **Direct Marketing:** Farm-to-consumer sales

Contact nearest Veterinary Hospital: 1962 (Toll-free)"""
            },
            
            # Storage & Processing
            'storage_processing': {
                'keywords': ['storage', 'warehouse', 'processing', 'value', 'addition', 'preservation', 'post-harvest'],
                'response': """🏪 POST-HARVEST MANAGEMENT & VALUE ADDITION:

**📦 SCIENTIFIC STORAGE:**

**🌾 GRAIN STORAGE:**
• **Moisture Content:** <14% for safe storage
• **Storage Structures:** Godowns, silos, bins
• **Fumigation:** Aluminum phosphide, methyl bromide
• **Capacity:** 50-1000 tons depending on need

**🧪 STORAGE CONDITIONS:**
• **Temperature:** 15-20°C ideal
• **Humidity:** <60% relative humidity
• **Ventilation:** Proper air circulation
• **Pest Control:** Regular monitoring & treatment

**🏗️ STORAGE INFRASTRUCTURE:**
• **FCI Warehouses:** Government storage facilities
• **Private Warehouses:** Commercial storage
• **Cold Storages:** Fruits, vegetables, dairy
• **Controlled Atmosphere:** Extended shelf life

**❄️ COLD STORAGE:**
• **Vegetables:** 0-4°C, 90-95% humidity
• **Fruits:** Variety-specific temperature
• **Dairy Products:** 2-4°C storage
• **Meat/Fish:** -18°C to -20°C freezing

**🔬 FOOD PROCESSING OPPORTUNITIES:**

**🌾 CEREALS PROCESSING:**
• **Rice Milling:** Paddy to rice, by-products
• **Flour Mills:** Wheat to flour, bran separation
• **Breakfast Cereals:** Corn flakes, puffed rice
• **Pasta/Noodles:** Value-added wheat products

**🥤 BEVERAGE INDUSTRY:**
• **Fruit Juices:** Fresh, concentrated, tetra pack
• **Dairy Beverages:** Flavored milk, lassi
• **Energy Drinks:** Sports nutrition segment
• **Traditional Drinks:** Buttermilk, coconut water

**🍯 SPECIALTY PRODUCTS:**
• **Organic Foods:** Certified organic processing
• **Herbal Products:** Medicinal plant processing
• **Spice Processing:** Grinding, blending, packaging
• **Honey Processing:** Filtration, bottling, branding

**💼 BUSINESS OPPORTUNITIES:**

**🏭 FOOD PROCESSING UNITS:**
• **Mini Rice Mills:** ₹5-10 lakh investment
• **Dal Mills:** Pulse processing, ₹8-15 lakh
• **Oil Mills:** Oilseed processing, ₹10-20 lakh
• **Pickle/Papad:** Home-based processing

**📊 MARKET LINKAGES:**
• **FPOs (Farmer Producer Organizations):** Collective processing
• **Contract Farming:** Assured procurement
• **Export Markets:** International quality standards
• **E-commerce Platforms:** Direct consumer sales

**💰 FINANCIAL SUPPORT:**
• **PMFME Scheme:** ₹10 lakh loan at 6% interest
• **Credit Linked Subsidy:** 35% for general category
• **NABARD Refinancing:** Processing unit loans
• **State Schemes:** Additional incentives

**🏆 QUALITY STANDARDS:**
• **FSSAI License:** Mandatory for food business
• **ISO Certification:** Quality management system
• **HACCP:** Hazard analysis critical control points
• **Organic Certification:** Premium market access

**📈 VALUE CHAIN DEVELOPMENT:**
• **Backward Integration:** Raw material supply
• **Forward Integration:** Marketing & distribution
• **Cluster Development:** Processing hubs
• **Technology Adoption:** Modern machinery

**🌱 EMERGING TRENDS:**
• **Ready-to-Eat Foods:** Convenience products
• **Functional Foods:** Health-focused products
• **Plant-Based Alternatives:** Vegan products
• **Sustainable Packaging:** Eco-friendly materials

Apply for PMFME scheme at: www.pmfme.gov.in"""
            },
            
            # Agricultural Marketing
            'marketing': {
                'keywords': ['marketing', 'brand', 'packaging', 'distribution', 'retail', 'wholesale', 'export'],
                'response': """🛒 AGRICULTURAL MARKETING & BRAND DEVELOPMENT:

**📱 DIGITAL MARKETING PLATFORMS:**
• **eNAM:** National Agriculture Market online
• **Amazon Kisan:** Direct farmer sales platform
• **Flipkart Samarth:** Rural products marketplace
• **Big Basket:** Fresh produce procurement
• **Ninjacart:** B2B agri-marketplace

**📦 PACKAGING & BRANDING:**
• **Primary Packaging:** Direct product contact
• **Secondary Packaging:** Transport & display
• **Tertiary Packaging:** Bulk transportation
• **Labeling:** Product information, nutrition facts
• **Branding:** Logo, tagline, unique identity

**🏪 MARKETING CHANNELS:**
• **Direct Marketing:** Farmer to consumer
• **Cooperative Marketing:** Through societies
• **Contract Farming:** Pre-agreed buyers
• **Retail Chains:** Supermarkets, hypermarkets
• **Export Markets:** International sales

**💰 PRICING STRATEGIES:**
• **Cost-Plus Pricing:** Production cost + margin
• **Market-Based Pricing:** According to demand-supply
• **Premium Pricing:** For organic/specialty products
• **Penetration Pricing:** Low price for market entry
• **Seasonal Pricing:** Based on availability

**🌐 EXPORT OPPORTUNITIES:**
• **Basmati Rice:** Major export earner (₹35,000 crores)
• **Spices:** Black pepper, cardamom, turmeric
• **Fruits:** Mangoes, grapes, pomegranates
• **Vegetables:** Onions, potatoes, green chillies
• **Processed Foods:** Ready-to-eat, organic products

**📋 EXPORT REQUIREMENTS:**
• **APEDA Registration:** Agricultural exports
• **FSSAI License:** Food safety certification
• **Phytosanitary Certificate:** Plant health
• **Certificate of Origin:** Country identification
• **Quality Certificates:** BIS, Agmark, organic

**🎯 TARGET MARKETS:**
• **Domestic Urban:** Metro cities, tier-2 cities
• **International:** UAE, USA, Europe, Japan
• **Institutional:** Hotels, restaurants, caterers
• **Processing Industries:** Food manufacturers
• **Online Consumers:** E-commerce buyers

**📊 MARKET RESEARCH:**
• **Consumer Preferences:** Taste, quality, packaging
• **Price Sensitivity:** Willingness to pay
• **Seasonal Demand:** Peak and off-seasons
• **Competition Analysis:** Other suppliers
• **Trend Analysis:** Emerging market segments

**🏆 QUALITY ASSURANCE:**
• **Agmark Standards:** Government quality certification
• **ISO Standards:** International quality norms
• **Organic Certification:** Chemical-free production
• **Fair Trade:** Ethical trading practices
• **Geographical Indications:** Unique regional products

**📱 TECHNOLOGY ADOPTION:**
• **QR Codes:** Product traceability
• **Digital Payments:** UPI, mobile wallets
• **CRM Systems:** Customer relationship management
• **ERP Software:** Business process automation
• **Social Media:** Facebook, Instagram marketing

**🤝 FARMER PRODUCER ORGANIZATIONS (FPOs):**
• **Collective Marketing:** Bulk sales advantage
• **Better Negotiation:** Strong market position
• **Quality Assurance:** Standardized production
• **Brand Building:** Common brand identity
• **Market Intelligence:** Shared information

**💡 SUCCESS STORIES:**
• **Sahyadri Farms:** Grape export from Maharashtra
• **HOPCOMS:** Karnataka vegetable marketing
• **Amul Model:** Dairy cooperative success
• **Farmer Fresh Zone:** Kerala vegetable delivery

Contact APEDA (agriexport.in) for export guidance!"""
            },
            
            # Technology & Innovation
            'technology': {
                'keywords': ['technology', 'digital', 'app', 'iot', 'sensor', 'ai', 'drone', 'precision', 'smart'],
                'response': """📱 AGRICULTURAL TECHNOLOGY & DIGITAL INNOVATION:

**🌾 PRECISION AGRICULTURE:**
• **GPS Technology:** Field mapping, auto-steering
• **Variable Rate Application:** Site-specific inputs
• **Yield Monitoring:** Real-time harvest data
• **Soil Sampling:** Grid-based nutrient analysis
• **Remote Sensing:** Satellite/drone imagery

**🔬 IoT SENSORS & MONITORING:**
• **Soil Sensors:** Moisture, pH, nutrients, temperature
• **Weather Stations:** Micro-climate monitoring
• **Crop Monitoring:** Growth stage tracking
• **Livestock Monitoring:** Health, location tracking
• **Water Management:** Automated irrigation systems

**🚁 DRONE APPLICATIONS:**
• **Crop Surveillance:** Disease/pest detection
• **Precision Spraying:** Targeted pesticide application
• **Seed Sowing:** Aerial seeding in difficult terrain
• **Crop Counting:** Plant population assessment
• **Irrigation Monitoring:** Water stress identification

**🤖 ARTIFICIAL INTELLIGENCE:**
• **Crop Disease Diagnosis:** Image-based identification
• **Yield Prediction:** ML algorithms for forecasting
• **Market Price Prediction:** Historical data analysis
• **Weather Forecasting:** Hyper-local predictions
• **Chatbots:** 24/7 farmer assistance

**📲 ESSENTIAL MOBILE APPS:**

**🌾 GOVERNMENT APPS:**
• **Kisan Suvidha:** Weather, market prices, plant protection
• **PMKISAN:** Scheme benefits, payment status
• **mKisan:** SMS-based advisories
• **Meghdoot:** Weather forecasting
• **Crop Insurance:** PMFBY claim status

**🌱 PRIVATE APPS:**
• **CropIn:** Farm management platform
• **AgroStar:** Crop advisory and input supply
• **DeHaat:** End-to-end farming solutions
• **BharatAgri:** Crop advisory and marketplace
• **Krishi Network:** Agricultural marketplace

**🌐 DIGITAL PLATFORMS:**
• **eNAM:** Online mandi platform
• **Digital Mandi:** Price discovery platform
• **AgriApp:** Comprehensive farming solutions
• **iKisan:** Agriculture portal and marketplace
• **Krishify:** Social network for farmers

**💻 FARM MANAGEMENT SOFTWARE:**
• **Field Records:** Crop history, input usage
• **Financial Tracking:** Income, expenses, profit
• **Inventory Management:** Seeds, fertilizers, tools
• **Labor Management:** Worker records, wages
• **Compliance Tracking:** Organic certification, GAP

**🛰️ SATELLITE TECHNOLOGY:**
• **ISRO's Bhuvan:** Crop area estimation
• **CROPWATCH:** Global crop monitoring
• **Sentinel Satellites:** European crop monitoring
• **NDVI Analysis:** Vegetation health assessment
• **Change Detection:** Land use monitoring

**⚡ RENEWABLE ENERGY:**
• **Solar Pumps:** Water lifting solutions
• **Solar Dryers:** Post-harvest processing
• **Biogas Plants:** Waste to energy conversion
• **Wind Mills:** Electricity generation
• **Solar Fencing:** Crop protection

**🏭 AUTOMATION SYSTEMS:**
• **Automated Irrigation:** Timer/sensor-based
• **Robotic Milking:** Dairy automation
• **Automated Feeding:** Livestock nutrition
• **Greenhouse Automation:** Climate control
• **Sorting Machines:** Post-harvest processing

**💡 EMERGING TECHNOLOGIES:**
• **Blockchain:** Supply chain traceability
• **5G Connectivity:** High-speed rural internet
• **Edge Computing:** Real-time data processing
• **Augmented Reality:** Training and diagnostics
• **Digital Twins:** Virtual farm modeling

**📊 DATA ANALYTICS:**
• **Big Data:** Pattern recognition in farming
• **Predictive Analytics:** Risk assessment
• **Prescriptive Analytics:** Actionable insights
• **Real-time Analytics:** Immediate decision making
• **Historical Analytics:** Trend analysis

**🎓 DIGITAL LITERACY:**
• **Farmer Training:** Technology adoption programs
• **Digital Payment:** UPI, mobile banking
• **Online Marketing:** E-commerce platforms
• **Information Access:** Weather, market, advisory
• **Skill Development:** Digital tools usage

Join Digital India Land Records Modernization for updated land records!"""
            },
        }
    
    def lemmatize_text(self, text):
        """Simple text preprocessing and lemmatization"""
        # Convert to lowercase and tokenize
        text = text.lower()
        tokens = word_tokenize(text)
        
        # Remove punctuation and stem words
        processed_tokens = []
        for token in tokens:
            if token.isalnum():  # Remove punctuation
                stemmed = self.stemmer.stem(token)
                processed_tokens.append(stemmed)
        
        return processed_tokens
    
    def find_best_match(self, user_input):
        """Find the best matching category based on keyword overlap"""
        user_tokens = self.lemmatize_text(user_input)
        
        best_match = None
        max_score = 0
        
        for category, data in self.knowledge_base.items():
            keywords = data['keywords']
            # Stem the keywords for comparison
            stemmed_keywords = [self.stemmer.stem(keyword.lower()) for keyword in keywords]
            
            # Calculate overlap score
            score = sum(1 for token in user_tokens if token in stemmed_keywords)
            
            # Boost score if exact keyword matches are found
            for keyword in keywords:
                if keyword.lower() in user_input.lower():
                    score += 2  # Exact match bonus
            
            if score > max_score:
                max_score = score
                best_match = category
        
        return best_match, max_score
    
    def get_response(self, user_input):
        """Get comprehensive response based on user input"""
        best_match, score = self.find_best_match(user_input)
        
        if score > 0 and best_match:
            return self.knowledge_base[best_match]['response']
        else:
            # Default comprehensive response
            return """🌾 **FarmGenie - Your Complete Agricultural Assistant**

I can help you with comprehensive farming guidance:

**🏛️ Government Schemes & Benefits:**
• PM-KISAN, PMFBY Insurance, PMKSY Irrigation
• Digital Agriculture Mission, KUSUM Solar
• Subsidies and financial assistance

**💰 Economic Support:**
• Market prices and MSP information
• Crop insurance and claim process
• Agricultural loans and KCC benefits
• Export opportunities and procedures

**🌱 Crop Management:**
• Seed selection and variety recommendations
• Fertilizer calculation and soil management
• Disease identification and treatment
• Organic farming and certification

**⚙️ Modern Technology:**
• Farm mechanization and equipment
• Precision agriculture and IoT
• Weather-based farming decisions
• Mobile apps and digital tools

**💧 Water Management:**
• Irrigation systems and efficiency
• Water conservation techniques
• Rainwater harvesting methods
• Drought management strategies

**📈 Value Addition & Marketing:**
• Post-harvest processing opportunities
• Food safety and quality standards
• Branding and packaging guidance
• Export procedures and documentation

**🐄 Livestock Integration:**
• Dairy farming and animal husbandry
• Integrated farming systems
• Animal health and nutrition
• Value-added dairy products

**Ask me specific questions like:**
• "What government schemes are available for small farmers?"
• "How to apply for crop insurance?"
• "Best fertilizer for wheat crop?"
• "How to start organic farming?"
• "What are the export opportunities for my produce?"

Type your specific farming question, and I'll provide detailed guidance! 🌾"""


# Updated Flask API endpoint with comprehensive chatbot
@app.route('/api/chat', methods=['POST'])
@login_required
def api_chat():
    """
    Enhanced Chat API endpoint with comprehensive agricultural knowledge base.
    Falls back to extensive pattern matching when AI API is unavailable.
    """
    try:
        data = request.get_json()
        
        if not data or 'messages' not in data:
            return jsonify({'error': 'Messages are required'}), 400
            
        messages = data.get('messages', [])
        
        if not messages:
            return jsonify({'error': 'At least one message is required'}), 400
        
        # Get the latest user message
        latest_message = messages[-1]['content'] if messages else ""
        
        # Enhanced agricultural context prompt
        system_prompt = """You are FarmGenie, an expert agricultural AI assistant specialized in Indian farming. You help with:

- Government schemes and subsidies (PM-KISAN, PMFBY, PMKSY)
- Crop recommendations and farming techniques
- Fertilizer and soil management advice  
- Disease and pest identification and treatment
- Market prices and economic guidance
- Weather-based farming decisions
- Agricultural technology and mechanization
- Sustainable and organic farming practices
- Livestock integration and dairy farming
- Export opportunities and value addition

Always provide practical, actionable advice suitable for Indian agricultural conditions. Use simple language and include specific product names, schemes, and contact details when helpful."""

        # Try using Cohere API first
        try:
            # Format chat history for Cohere API
            chat_history = []
            if len(messages) > 1:
                for msg in messages[:-1]:  # Exclude the current message
                    role = "USER" if msg["role"] == "user" else "CHATBOT"
                    chat_history.append({
                        "role": role,
                        "message": msg["content"]
                    })
            
            # Prepare the API request
            api_data = {
                "model": "command-r-plus",
                "message": latest_message,
                "preamble": system_prompt,
                "max_tokens": 1000,
                "temperature": 0.7
            }
            
            # Add chat history only if it exists
            if chat_history:
                api_data["chat_history"] = chat_history[-10:]  # Limit to last 10
            
            print(f"Sending to Cohere API: {json.dumps(api_data, indent=2)}")  # Debug log
            
            cohere_response = requests.post(
                "https://api.cohere.ai/v1/chat",
                headers={
                    "Authorization": f"Bearer {app.config['COHERE_API_KEY']}",
                    "Content-Type": "application/json"
                },
                json=api_data,
                timeout=30
            )
            
            print(f"Cohere API Response Status: {cohere_response.status_code}")  # Debug log
            print(f"Cohere API Response: {cohere_response.text}")  # Debug log
            
            if cohere_response.status_code == 200:
                cohere_data = cohere_response.json()
                ai_response = cohere_data.get('text', 'Sorry, I could not generate a response.')
                
                # Detect language
                detected_lang = detect_language(latest_message)
                
                return jsonify({
                    'response': ai_response,
                    'language': detected_lang,
                    'status': 'success'
                })
            else:
                print(f"Cohere API error: {cohere_response.status_code} - {cohere_response.text}")
                # Fallback to comprehensive knowledge base
                chatbot = ComprehensiveAgriChatbot()
                fallback_response = chatbot.get_response(latest_message)
                return jsonify({
                    'response': fallback_response,
                    'language': 'en',
                    'status': 'comprehensive_fallback'
                })
                
        except Exception as api_error:
            print(f"Cohere API exception: {str(api_error)}")
            # Fallback to comprehensive knowledge base
            chatbot = ComprehensiveAgriChatbot()
            fallback_response = chatbot.get_response(latest_message)
            return jsonify({
                'response': fallback_response,
                'language': 'en',
                'status': 'comprehensive_fallback'
            })
        
    except Exception as e:
        print(f"Chat API error: {str(e)}")
        return jsonify({
            'response': 'I apologize, but I am experiencing technical difficulties. Please try again or contact our support team.',
            'language': 'en',
            'status': 'error'
        }), 500


def detect_language(text):
    """Enhanced language detection for agricultural context"""
    hindi_words = ['किसान', 'खेती', 'फसल', 'खाद', 'बीज', 'पानी', 'मिट्टी', 'रोग', 'सरकार', 'योजना', 'सब्सिडी', 'बीमा']
    odia_words = ['କୃଷକ', 'ଚାଷ', 'ଫସଲ', 'ସାର', 'ବିହନ', 'ଜଳ', 'ମାଟି', 'ରୋଗ']
    punjabi_words = ['ਕਿਸਾਨ', 'ਖੇਤੀ', 'ਫ਼ਸਲ', 'ਖਾਦ', 'ਬੀਜ', 'ਪਾਣੀ', 'ਮਿੱਟੀ']
    bengali_words = ['কৃষক', 'চাষ', 'ফসল', 'সার', 'বীজ', 'পানি', 'মাটি', 'রোগ']
    tamil_words = ['விவசாயி', 'வேளாண்மை', 'பயிர்', 'உர', 'விதை', 'நீர்', 'மண்']
    
    if any(word in text for word in hindi_words):
        return 'hi'
    elif any(word in text for word in odia_words):
        return 'or' 
    elif any(word in text for word in punjabi_words):
        return 'pa'
    elif any(word in text for word in bengali_words):
        return 'bn'
    elif any(word in text for word in tamil_words):
        return 'ta'
    else:
        return 'en'


# disease_info.py - Comprehensive disease information database
DISEASE_INFO = {
    "Apple scab": {
        "description": "Apple scab is a fungal disease that affects apple trees, causing dark, scaly lesions on leaves, fruit, and twigs.",
        "causes": [
            "Caused by the fungus Venturia inaequalis",
            "Thrives in cool, moist conditions (60-75°F with high humidity)",
            "Spreads through airborne spores released from infected fallen leaves",
            "Rain and dew provide moisture needed for spore germination",
            "Poor air circulation around trees increases risk",
            "Overcrowded plantings create favorable conditions"
        ],
        "symptoms": [
            "Dark, olive-green to black spots on leaves",
            "Scaly, rough lesions on fruit surface",
            "Premature leaf drop in severe cases",
            "Reduced fruit quality and marketability",
            "Twig lesions that can girdle branches"
        ],
        "prevention": [
            "Plant scab-resistant apple varieties",
            "Ensure proper spacing for good air circulation",
            "Remove and destroy fallen leaves in autumn",
            "Prune trees to improve air flow",
            "Avoid overhead watering when possible",
            "Apply preventive fungicide sprays in early spring"
        ],
        "treatment": [
            "Apply fungicides containing myclobutanil, captan, or sulfur",
            "Spray at green tip, pink bud, petal fall, and first cover stages",
            "Remove infected plant parts and dispose properly",
            "Improve drainage around tree base",
            "Consider organic treatments like neem oil or copper fungicides",
            "Maintain tree health through proper fertilization"
        ],
        "organic_solutions": [
            "Baking soda spray (1 tsp per quart water)",
            "Neem oil applications every 7-14 days",
            "Copper-based fungicides for organic management",
            "Compost tea to boost plant immunity",
            "Beneficial microorganism applications"
        ]
    },
    
    "Black rot": {
        "description": "Black rot affects multiple crops including apples and grapes, causing severe fruit and leaf damage.",
        "causes": [
            "Fungal pathogens: Botryosphaeria obtusa (apple), Guignardia bidwellii (grape)",
            "Warm, humid weather conditions (75-85°F)",
            "Wounds in plant tissue from insects or pruning",
            "Poor air circulation and overcrowding",
            "Infected plant debris left in the field",
            "Stress factors like drought or nutrient deficiency"
        ],
        "symptoms": [
            "Circular, dark brown to black lesions on fruit",
            "Concentric rings in lesions (bull's-eye pattern)",
            "Fruit becomes mummified and shriveled",
            "Brown leaf spots with yellow halos",
            "Cankers on branches and stems"
        ],
        "prevention": [
            "Remove and destroy infected fruit and plant debris",
            "Prune during dry weather to reduce wound infection",
            "Improve air circulation through proper spacing",
            "Avoid overhead irrigation during fruit development",
            "Maintain tree/vine health through balanced nutrition",
            "Use disease-free planting material"
        ],
        "treatment": [
            "Apply fungicides containing tebuconazole, myclobutanil, or thiophanate-methyl",
            "Begin treatments at bloom and continue through harvest",
            "Remove mummified fruits and infected plant parts",
            "Copper-based fungicides for early season protection",
            "Systemic fungicides for established infections",
            "Sanitize pruning tools between plants"
        ],
        "organic_solutions": [
            "Bordeaux mixture (copper sulfate + lime)",
            "Potassium bicarbonate sprays",
            "Essential oil-based fungicides",
            "Biocontrol agents like Bacillus subtilis",
            "Proper sanitation and cultural practices"
        ]
    },
    
    "Cedar apple rust": {
        "description": "A fungal disease that requires both apple and cedar trees to complete its life cycle.",
        "causes": [
            "Caused by Gymnosporangium juniperi-virginianae",
            "Requires alternate hosts: apple trees and cedar/juniper trees",
            "Spores travel between hosts via wind and rain",
            "Cool, wet spring conditions favor infection",
            "Proximity to cedar or juniper trees increases risk",
            "Two-year life cycle alternating between hosts"
        ],
        "symptoms": [
            "Bright orange-yellow spots on apple leaves",
            "Orange gelatinous horns on cedar trees in spring",
            "Premature defoliation of apple trees",
            "Reduced fruit quality and yield",
            "Circular lesions with orange centers on fruit"
        ],
        "prevention": [
            "Plant rust-resistant apple varieties",
            "Remove cedar and juniper trees within 2 miles if possible",
            "Improve air circulation around apple trees",
            "Avoid overhead watering during spring",
            "Apply preventive fungicide sprays",
            "Monitor weather conditions for infection periods"
        ],
        "treatment": [
            "Fungicides containing myclobutanil, propiconazole, or triadimefon",
            "Apply at pink bud, bloom, petal fall, and first cover",
            "Remove infected leaves and fruit",
            "Treat both apple and cedar hosts if possible",
            "Continue treatments through summer for severe infections",
            "Use systemic fungicides for better control"
        ],
        "organic_solutions": [
            "Sulfur-based fungicides",
            "Copper fungicides applied early in season",
            "Neem oil for mild infections",
            "Remove alternate hosts where feasible",
            "Encourage beneficial insects and natural predators"
        ]
    },

    "Powdery mildew": {
        "description": "A common fungal disease affecting many plants, creating a white powdery coating on leaves.",
        "causes": [
            "Various fungal species including Erysiphe, Podosphaera, and Uncinula",
            "Moderate temperatures (60-80°F) with high humidity",
            "Poor air circulation and overcrowding",
            "Shade and low light conditions",
            "High nitrogen levels promoting tender growth",
            "Dry soil conditions with humid air"
        ],
        "symptoms": [
            "White or gray powdery coating on leaves, stems, and buds",
            "Yellowing and distortion of affected leaves",
            "Stunted growth and reduced vigor",
            "Premature leaf drop in severe cases",
            "Reduced flowering and fruit production"
        ],
        "prevention": [
            "Plant resistant varieties when available",
            "Ensure adequate spacing for air circulation",
            "Avoid overhead watering, especially in evening",
            "Remove infected plant debris regularly",
            "Avoid excessive nitrogen fertilization",
            "Provide adequate sunlight and ventilation"
        ],
        "treatment": [
            "Fungicides containing myclobutanil, propiconazole, or sulfur",
            "Apply at first sign of disease symptoms",
            "Horticultural oils can smother fungal spores",
            "Remove severely infected plant parts",
            "Improve growing conditions and air flow",
            "Apply treatments every 7-14 days as needed"
        ],
        "organic_solutions": [
            "Baking soda solution (1 tbsp per gallon water)",
            "Milk spray (1 part milk to 9 parts water)",
            "Neem oil applications",
            "Sulfur dust or spray",
            "Potassium bicarbonate treatments"
        ]
    },

    "Cercospora leaf spot Gray leaf spot": {
        "description": "A fungal disease affecting corn, causing distinctive rectangular lesions on leaves.",
        "causes": [
            "Caused by Cercospora zeae-maydis fungus",
            "High humidity and warm temperatures (80-90°F)",
            "Extended periods of leaf wetness",
            "Poor air circulation in dense plantings",
            "Infected crop residue from previous season",
            "Continuous corn production in the same field"
        ],
        "symptoms": [
            "Gray to tan rectangular lesions parallel to leaf veins",
            "Lesions may have yellow halos",
            "Severe defoliation in advanced stages",
            "Reduced photosynthetic capacity",
            "Premature plant death in severe cases"
        ],
        "prevention": [
            "Rotate crops to break disease cycle",
            "Till or bury crop residue after harvest",
            "Plant resistant corn hybrids",
            "Avoid overhead irrigation when possible",
            "Maintain proper plant spacing",
            "Monitor fields regularly during growing season"
        ],
        "treatment": [
            "Foliar fungicides containing azoxystrobin, propiconazole, or pyraclostrobin",
            "Apply at first disease symptoms or tasseling",
            "Multiple applications may be needed in wet seasons",
            "Time applications based on weather conditions",
            "Consider aerial application for large fields",
            "Combine with good cultural practices"
        ],
        "organic_solutions": [
            "Copper-based fungicides",
            "Biological control agents",
            "Crop rotation with non-host plants",
            "Enhanced soil organic matter",
            "Beneficial microorganism applications"
        ]
    },

    "Common rust": {
        "description": "A fungal disease of corn causing rust-colored pustules on leaves.",
        "causes": [
            "Caused by Puccinia sorghi fungus",
            "Cool, moist weather conditions (60-75°F)",
            "High humidity and dew formation",
            "Spores carried by wind from infected plants",
            "Alternate host: wood sorrel (Oxalis species)",
            "Extended periods of leaf wetness"
        ],
        "symptoms": [
            "Small, circular to oval rust-colored pustules on leaves",
            "Pustules primarily on upper leaf surface",
            "Leaves may yellow and die prematurely",
            "Reduced plant vigor and yield",
            "Pustules may also appear on husks and stalks"
        ],
        "prevention": [
            "Plant resistant corn hybrids",
            "Avoid excessive nitrogen fertilization",
            "Remove volunteer corn and weeds",
            "Monitor weather conditions for favorable disease periods",
            "Ensure good air circulation in plantings",
            "Control alternate hosts where possible"
        ],
        "treatment": [
            "Foliar fungicides if economic threshold is reached",
            "Azoxystrobin, propiconazole, or tebuconazole-based products",
            "Apply when 50% of plants have pustules before tasseling",
            "Consider treatment timing based on growth stage",
            "Multiple applications may be needed",
            "Cost-benefit analysis important for treatment decisions"
        ],
        "organic_solutions": [
            "Copper fungicides for early infections",
            "Neem oil applications",
            "Biological control agents",
            "Resistant varieties as primary control",
            "Cultural practices to reduce disease pressure"
        ]
    },

    "Northern Leaf Blight": {
        "description": "A fungal disease of corn causing large, elongated lesions on leaves.",
        "causes": [
            "Caused by Exserohilum turcicum (Setosphaeria turcica)",
            "Moderate temperatures (64-81°F) with high humidity",
            "Extended leaf wetness periods",
            "Infected corn residue from previous crops",
            "Dense plant populations with poor air circulation",
            "Susceptible corn hybrids"
        ],
        "symptoms": [
            "Large, elongated gray-green to tan lesions on leaves",
            "Lesions are 1-6 inches long, cigar-shaped",
            "Dark sporulation may be visible in lesions",
            "Lesions can coalesce and kill entire leaves",
            "Reduced grain fill and yield loss"
        ],
        "prevention": [
            "Plant resistant corn hybrids",
            "Rotate with non-host crops",
            "Bury or till crop residue after harvest",
            "Avoid excessive nitrogen fertilization",
            "Maintain proper plant population and spacing",
            "Scout fields regularly during growing season"
        ],
        "treatment": [
            "Foliar fungicides containing azoxystrobin, pyraclostrobin, or propiconazole",
            "Apply at first disease symptoms or V8-VT growth stages",
            "Multiple applications may be necessary",
            "Consider economic threshold before treatment",
            "Tank mix compatibility with other inputs",
            "Timing based on disease pressure and weather"
        ],
        "organic_solutions": [
            "Copper-based fungicides",
            "Biological fungicides with Bacillus species",
            "Crop rotation as primary control",
            "Enhanced soil biology through organic matter",
            "Resistant varieties as first line of defense"
        ]
    },

    "Esca (Black Measles)": {
        "description": "A complex fungal disease affecting grapevines, causing leaf symptoms and wood decay.",
        "causes": [
            "Complex of fungi including Phaeomoniella chlamydospora and Phaeoacremonium species",
            "Pruning wounds provide entry points",
            "Mature vines (>8 years old) more susceptible",
            "Mechanical injuries and insect damage",
            "Stress factors like drought or nutrient imbalance",
            "Infected propagation material"
        ],
        "symptoms": [
            "'Tiger stripe' pattern on leaves (yellow stripes between veins)",
            "Leaf necrosis and early defoliation",
            "Berry shrinkage and dark spots on fruit",
            "White rot in wood with black streaking",
            "Reduced vine vigor and yield",
            "Apoplexy (sudden vine collapse) in severe cases"
        ],
        "prevention": [
            "Prune during dry weather conditions",
            "Protect pruning wounds with paste or paint",
            "Use disease-free propagation material",
            "Maintain vine health through proper nutrition",
            "Avoid mechanical damage to trunks",
            "Remove and destroy infected wood"
        ],
        "treatment": [
            "Currently no curative chemical treatments available",
            "Trunk surgery to remove infected wood",
            "Sodium arsenite injections (where legally permitted)",
            "Biological control agents under development",
            "Focus on prevention and cultural practices",
            "Replace severely affected vines"
        ],
        "organic_solutions": [
            "Trichoderma-based biological treatments",
            "Wound protection with natural compounds",
            "Enhanced vine nutrition with organic amendments",
            "Proper pruning techniques and timing",
            "Biocontrol research ongoing"
        ]
    },

    "Leaf blight (Isariopsis Leaf Spot)": {
        "description": "A fungal disease affecting grapes, causing leaf spots and defoliation.",
        "causes": [
            "Caused by Pseudocercospora vitis (formerly Isariopsis clavispora)",
            "Warm, humid conditions favor development",
            "Poor air circulation in dense canopies",
            "Extended periods of leaf wetness",
            "Infected plant debris from previous season",
            "Stressed or weakened vines"
        ],
        "symptoms": [
            "Small, dark brown to black spots on leaves",
            "Spots may have yellow halos",
            "Leaves turn yellow and drop prematurely",
            "Reduced photosynthetic capacity",
            "Weakened vine vigor",
            "Potential impact on fruit quality"
        ],
        "prevention": [
            "Improve air circulation through proper pruning",
            "Remove infected leaves and debris",
            "Avoid overhead irrigation when possible",
            "Maintain proper vine spacing",
            "Monitor weather conditions for infection periods",
            "Keep vineyard floor clean"
        ],
        "treatment": [
            "Fungicides containing copper, mancozeb, or strobilurins",
            "Apply preventively during favorable weather",
            "Multiple applications may be needed",
            "Remove infected plant material",
            "Improve cultural practices",
            "Time applications based on disease pressure"
        ],
        "organic_solutions": [
            "Copper-based fungicides",
            "Biological control agents",
            "Compost tea applications",
            "Enhanced air circulation",
            "Organic matter to improve soil health"
        ]
    },

    "Haunglongbing (Citrus greening)": {
        "description": "A devastating bacterial disease of citrus trees transmitted by psyllid insects.",
        "causes": [
            "Caused by Candidatus Liberibacter asiaticus bacteria",
            "Transmitted primarily by Asian citrus psyllid (Diaphorina citri)",
            "Also spread through infected plant material",
            "Cannot be cured once established",
            "Warm, humid climates favor disease development",
            "Movement of infected plants spreads disease"
        ],
        "symptoms": [
            "Yellow shoots and blotchy mottling on leaves",
            "Asymmetrical leaf yellowing across midrib",
            "Small, lopsided fruit with thick, pale rind",
            "Bitter, unusable fruit",
            "Tree decline and eventual death",
            "Stunted growth and reduced yield"
        ],
        "prevention": [
            "Control psyllid vectors with targeted insecticides",
            "Remove and destroy infected trees immediately",
            "Use certified disease-free nursery stock",
            "Implement quarantine measures",
            "Regular scouting and early detection",
            "Avoid moving plant material from infected areas"
        ],
        "treatment": [
            "No cure currently available",
            "Remove infected trees to prevent spread",
            "Vector control is primary management strategy",
            "Nutritional support may slow decline",
            "Antibiotic treatments (oxytetracycline) in some regions",
            "Research ongoing for resistant varieties"
        ],
        "organic_solutions": [
            "Biological control of psyllid vectors",
            "Beneficial insects to control psyllids",
            "Organic-approved insecticides for vector control",
            "Tree removal is still necessary",
            "Focus on prevention through vector management"
        ]
    },

    "Bacterial spot": {
        "description": "A bacterial disease affecting multiple crops including tomatoes, peppers, and stone fruits.",
        "causes": [
            "Caused by Xanthomonas species bacteria",
            "Warm, humid weather with temperatures 75-86°F",
            "Rain and overhead irrigation spread bacteria",
            "Wounds from insects, pruning, or weather damage",
            "Contaminated seeds or transplants",
            "Poor sanitation practices"
        ],
        "symptoms": [
            "Small, dark brown to black spots on leaves",
            "Spots may have yellow halos",
            "Fruit lesions are raised, dark, and scabby",
            "Severe defoliation in advanced cases",
            "Reduced fruit quality and marketability",
            "Cankers on stems and branches"
        ],
        "prevention": [
            "Use certified disease-free seeds and transplants",
            "Avoid overhead irrigation",
            "Provide adequate plant spacing for air circulation",
            "Remove infected plant debris",
            "Rotate crops with non-host plants",
            "Disinfect tools and equipment"
        ],
        "treatment": [
            "Copper-based bactericides (copper sulfate, copper hydroxide)",
            "Streptomycin (where legally permitted)",
            "Apply preventively before disease symptoms appear",
            "Combine with spreader-stickers for better coverage",
            "Remove infected plant parts",
            "Improve growing conditions to reduce stress"
        ],
        "organic_solutions": [
            "Copper-based bactericides",
            "Biological control agents (Bacillus subtilis)",
            "Proper sanitation and cultural practices",
            "Resistant varieties when available",
            "Compost tea for plant health"
        ]
    },

    "Early blight": {
        "description": "A common fungal disease affecting tomatoes and potatoes, causing leaf spots and fruit rot.",
        "causes": [
            "Caused by Alternaria solani fungus",
            "Warm, humid weather conditions (75-85°F)",
            "Extended periods of leaf wetness",
            "Plant stress from drought, nutrient deficiency, or damage",
            "Poor air circulation",
            "Infected plant debris in soil"
        ],
        "symptoms": [
            "Dark, concentric ring spots on older leaves",
            "Target-like lesions with bull's-eye appearance",
            "Yellowing and death of affected leaves",
            "Stem lesions and girdling near soil line",
            "Dark, sunken lesions on fruit",
            "Reduced plant vigor and yield"
        ],
        "prevention": [
            "Rotate crops with non-solanaceous plants",
            "Remove infected plant debris",
            "Provide adequate plant spacing",
            "Avoid overhead watering",
            "Maintain plant health through proper nutrition",
            "Use disease-free seeds and transplants"
        ],
        "treatment": [
            "Fungicides containing chlorothalonil, azoxystrobin, or boscalid",
            "Begin applications early in season",
            "Continue treatments on 7-14 day intervals",
            "Remove infected plant parts",
            "Improve air circulation around plants",
            "Apply mulch to reduce soil splashing"
        ],
        "organic_solutions": [
            "Copper-based fungicides",
            "Baking soda sprays",
            "Neem oil applications",
            "Biological fungicides with Bacillus species",
            "Compost tea for disease suppression"
        ]
    },

    "Late blight": {
        "description": "A devastating disease of tomatoes and potatoes caused by a water mold pathogen.",
        "causes": [
            "Caused by Phytophthora infestans (water mold, not true fungus)",
            "Cool, wet weather conditions (60-70°F with high humidity)",
            "Extended periods of leaf wetness",
            "Wind-dispersed spores from infected plants",
            "Contaminated potato seed tubers",
            "Poor air circulation and overcrowding"
        ],
        "symptoms": [
            "Water-soaked, dark green to brown lesions on leaves",
            "White, fuzzy growth on undersides of leaves",
            "Rapid spread and plant death in favorable conditions",
            "Dark, firm rot on potato tubers",
            "Brown, firm lesions on tomato fruit",
            "Distinctive musty odor from infected plants"
        ],
        "prevention": [
            "Plant certified disease-free seed potatoes",
            "Ensure good air circulation",
            "Avoid overhead watering, especially in evening",
            "Remove infected plant material immediately",
            "Monitor weather for favorable disease conditions",
            "Use resistant varieties when available"
        ],
        "treatment": [
            "Fungicides containing metalaxyl, mefenoxam, or cymoxanil",
            "Apply preventively before disease appearance",
            "Systemic and contact fungicides for best control",
            "Multiple applications needed in wet weather",
            "Remove and destroy infected plants immediately",
            "Act quickly as disease spreads rapidly"
        ],
        "organic_solutions": [
            "Copper-based fungicides applied preventively",
            "Biological control agents",
            "Cultural practices are most important",
            "Remove infected plants immediately",
            "Improve air circulation and drainage"
        ]
    },

    "Leaf Mold": {
        "description": "A fungal disease primarily affecting greenhouse tomatoes, causing yellow leaf spots.",
        "causes": [
            "Caused by Passalora fulva (formerly Fulvia fulva)",
            "High humidity (>85%) with poor air circulation",
            "Moderate temperatures (70-75°F)",
            "Greenhouse or protected growing environments",
            "Dense plant canopies restricting airflow",
            "Extended periods of leaf wetness"
        ],
        "symptoms": [
            "Yellow spots on upper leaf surfaces",
            "Olive-green to brown fuzzy growth on leaf undersides",
            "Leaves turn brown and die from bottom up",
            "Reduced photosynthetic capacity",
            "Rarely affects fruit directly",
            "Severe defoliation in advanced cases"
        ],
        "prevention": [
            "Maintain humidity below 85%",
            "Ensure adequate ventilation",
            "Space plants properly for air circulation",
            "Remove lower leaves touching soil",
            "Avoid overhead watering",
            "Use resistant tomato varieties"
        ],
        "treatment": [
            "Improve ventilation and reduce humidity",
            "Fungicides containing azoxystrobin, boscalid, or cyprodinil",
            "Remove infected leaves promptly",
            "Apply treatments early in disease development",
            "Adjust watering practices",
            "Consider biological control agents"
        ],
        "organic_solutions": [
            "Bacillus subtilis-based biofungicides",
            "Improved air circulation",
            "Reduced humidity through ventilation",
            "Milk sprays for mild infections",
            "Cultural control is most effective"
        ]
    },

    "Septoria leaf spot": {
        "description": "A fungal disease of tomatoes causing numerous small, dark spots on leaves.",
        "causes": [
            "Caused by Septoria lycopersici fungus",
            "Warm, wet weather conditions",
            "High humidity and extended leaf wetness",
            "Splash dispersal from rain or irrigation",
            "Infected plant debris in soil",
            "Poor air circulation around plants"
        ],
        "symptoms": [
            "Numerous small, circular spots with gray centers",
            "Dark brown to black borders around spots",
            "Tiny black specks (pycnidia) in spot centers",
            "Yellowing and death of affected leaves",
            "Disease progresses from bottom leaves upward",
            "Severe defoliation reduces fruit quality"
        ],
        "prevention": [
            "Remove infected plant debris",
            "Provide adequate plant spacing",
            "Use drip irrigation instead of overhead watering",
            "Apply mulch to reduce soil splashing",
            "Stake and prune plants for better air circulation",
            "Rotate crops with non-solanaceous plants"
        ],
        "treatment": [
            "Fungicides containing chlorothalonil, azoxystrobin, or pyraclostrobin",
            "Begin applications at first disease symptoms",
            "Continue on 10-14 day intervals",
            "Remove infected lower leaves",
            "Improve air circulation",
            "Apply treatments in early morning or evening"
        ],
        "organic_solutions": [
            "Copper-based fungicides",
            "Baking soda sprays (1 tbsp per gallon)",
            "Neem oil applications",
            "Biological control with Bacillus species",
            "Cultural practices are most important"
        ]
    },

    "Spider mites Two-spotted spider mite": {
        "description": "Tiny arachnids that feed on plant sap, causing stippling and webbing on leaves.",
        "causes": [
            "Two-spotted spider mites (Tetranychus urticae)",
            "Hot, dry weather conditions",
            "Low humidity favors reproduction",
            "Dusty conditions",
            "Overuse of broad-spectrum insecticides killing predators",
            "Stressed plants more susceptible"
        ],
        "symptoms": [
            "Fine stippling or speckling on leaf surfaces",
            "Leaves may appear bronze or yellow",
            "Fine webbing on leaves and stems",
            "Tiny moving dots on undersides of leaves",
            "Premature leaf drop in severe infestations",
            "Reduced plant vigor and yield"
        ],
        "prevention": [
            "Maintain adequate soil moisture",
            "Increase humidity around plants",
            "Avoid dusty conditions",
            "Preserve beneficial predatory mites and insects",
            "Regular monitoring and early detection",
            "Remove heavily infested plant parts"
        ],
        "treatment": [
            "Miticides containing abamectin, bifenthrin, or spiromesifen",
            "Insecticidal soaps and horticultural oils",
            "Predatory mites as biological control",
            "High-pressure water sprays to dislodge mites",
            "Rotate miticide classes to prevent resistance",
            "Target undersides of leaves where mites hide"
        ],
        "organic_solutions": [
            "Predatory mites (Phytoseiulus persimilis)",
            "Insecticidal soap sprays",
            "Neem oil applications",
            "Horticultural oils",
            "Beneficial insects like ladybugs and lacewings"
        ]
    },

    "Target Spot": {
        "description": "A fungal disease of tomatoes causing circular spots with concentric rings.",
        "causes": [
            "Caused by Corynespora cassiicola fungus",
            "Warm, humid weather conditions",
            "Extended periods of leaf wetness",
            "Poor air circulation",
            "Infected plant debris",
            "Splash dispersal from rain or irrigation"
        ],
        "symptoms": [
            "Circular to oval spots with concentric rings",
            "Brown to dark brown lesions with light centers",
            "Spots on leaves, stems, and fruit",
            "Yellow halos around lesions",
            "Defoliation starting from lower leaves",
            "Reduced fruit quality and yield"
        ],
        "prevention": [
            "Improve air circulation around plants",
            "Remove infected plant debris",
            "Use drip irrigation to avoid leaf wetness",
            "Provide adequate plant spacing",
            "Rotate crops with non-host plants",
            "Apply preventive fungicide sprays"
        ],
        "treatment": [
            "Fungicides containing azoxystrobin, pyraclostrobin, or boscalid",
            "Begin applications at first disease symptoms",
            "Continue treatments on regular intervals",
            "Remove infected plant parts",
            "Improve cultural practices",
            "Ensure good spray coverage"
        ],
        "organic_solutions": [
            "Copper-based fungicides",
            "Biological control agents",
            "Cultural practices to reduce leaf wetness",
            "Neem oil for mild infections",
            "Compost tea applications"
        ]
    },

    "Tomato Yellow Leaf Curl Virus": {
        "description": "A viral disease transmitted by whiteflies, causing leaf curling and stunting.",
        "causes": [
            "Tomato yellow leaf curl virus (TYLCV)",
            "Transmitted by silverleaf whitefly (Bemisia tabaci)",
            "Cannot be cured once plants are infected",
            "Warm weather favors whitefly reproduction",
            "Introduction of infected plants",
            "Weed hosts harbor virus and vectors"
        ],
        "symptoms": [
            "Upward curling of leaf margins",
            "Yellowing of young leaves",
            "Stunted plant growth",
            "Reduced fruit set and size",
            "Thickened, leathery leaf texture",
            "Shortened internodes"
        ],
        "prevention": [
            "Control whitefly vectors with insecticides",
            "Use reflective mulches to repel whiteflies",
            "Remove weeds that serve as virus hosts",
            "Use virus-resistant tomato varieties",
            "Exclude whiteflies with row covers",
            "Monitor and remove infected plants"
        ],
        "treatment": [
            "No cure available once plants are infected",
            "Remove infected plants to prevent spread",
            "Control whitefly vectors",
            "Focus on prevention strategies",
            "Use resistant varieties in affected areas",
            "Manage alternative hosts and weeds"
        ],
        "organic_solutions": [
            "Biological control of whiteflies",
            "Beneficial insects like Encarsia formosa",
            "Reflective mulches",
            "Physical barriers and row covers",
            "Weed management around crops"
        ]
    },

    "Tomato mosaic virus": {
        "description": "A viral disease causing mosaic patterns on tomato leaves and stunted growth.",
        "causes": [
            "Tomato mosaic virus (ToMV)",
            "Transmitted through infected seeds, tools, and hands",
            "Very stable virus surviving in plant debris",
            "Mechanical transmission through plant handling",
            "Contaminated greenhouse structures",
            "No insect vectors required"
        ],
        "symptoms": [
            "Light and dark green mosaic pattern on leaves",
            "Leaf distortion and puckering",
            "Stunted plant growth",
            "Reduced fruit yield and quality",
            "Fruit may show color variations",
            "Internal browning of fruit"
        ],
        "prevention": [
            "Use certified virus-free seeds",
            "Sanitize tools and hands between plants",
            "Avoid smoking around tomato plants",
            "Remove infected plants immediately",
            "Disinfect greenhouse structures",
            "Control weeds that may harbor virus"
        ],
        "treatment": [
            "No cure available for infected plants",
            "Remove and destroy infected plants",
            "Strict sanitation protocols",
            "Use resistant varieties where available",
            "Focus on prevention measures",
            "Disinfect tools with 10% bleach solution"
        ],
        "organic_solutions": [
            "Strict sanitation practices",
            "Milk sprays may provide some protection",
            "Remove infected plants promptly",
            "Use virus-free planting material",
            "Biological control not applicable for viruses"
        ]
    },

    "Leaf scorch": {
        "description": "A physiological disorder or fungal disease causing browning and drying of leaf edges.",
        "causes": [
            "Environmental stress (heat, drought, wind)",
            "Salt accumulation in soil or water",
            "Nutrient deficiencies (potassium, magnesium)",
            "Root damage from cultivation or pests",
            "Fungal pathogens in some cases",
            "Chemical burn from fertilizers or pesticides"
        ],
        "symptoms": [
            "Brown, crispy margins on leaves",
            "Yellowing between veins",
            "Premature leaf drop",
            "Reduced plant vigor",
            "Symptoms often worse on older leaves",
            "May progress inward from leaf edges"
        ],
        "prevention": [
            "Maintain consistent soil moisture",
            "Provide shade during extreme heat",
            "Test and improve soil drainage",
            "Monitor and adjust fertilizer applications",
            "Protect from strong winds",
            "Regular soil and water testing"
        ],
        "treatment": [
            "Improve watering practices",
            "Add organic matter to improve soil",
            "Adjust fertilizer program",
            "Provide temporary shade if heat-related",
            "Remove severely affected leaves",
            "Address underlying soil or water issues"
        ],
        "organic_solutions": [
            "Compost and organic matter additions",
            "Mulching to conserve moisture",
            "Natural wind barriers",
            "Foliar feeding with liquid kelp",
            "Proper irrigation management"
        ]
    }
}

# Enhanced Flask route with detailed disease information
@app.route('/disease', methods=['GET', 'POST'])
@login_required
def disease():
    form = DiseaseForm()
    theme = request.args.get('theme', 'bright')
    
    if form.validate_on_submit():
        filename = secure_filename(form.image.data.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        form.image.data.save(filepath)
        
        # Load and predict
        image = Image.open(filepath)
        predictions = import_and_predict(image, model5)
        
        # Load class indices
        with open(os.path.join(MODEL_DIR, "class_indices.json"), "r") as f:
            class_indices = json.load(f)
        
        classes = list(class_indices.keys())
        classresult = np.argmax(predictions, axis=1)[0]
        confidence = float(np.max(predictions, axis=1)[0])
        
        # Parse prediction
        word = classes[classresult].split("___")
        crop = word[0].replace("_", " ")
        condition = word[1].replace("_", " ")
        
        # Get detailed information
        disease_details = get_disease_details(condition, crop, confidence)
        
        # Create comprehensive output
        output = create_detailed_output(crop, condition, disease_details, confidence)
        
        # Save prediction to database
        pred = Prediction(
            user_id=current_user.id, 
            type='disease', 
            inputs=json.dumps({
                'image': filename,
                'crop': crop,
                'condition': condition,
                'confidence': confidence
            }), 
            output=output[:500]  # Truncate for database storage
        )
        db.session.add(pred)
        db.session.commit()
        
        return render_template('disease.html', 
                             form=form, 
                             result=output,
                             disease_info=disease_details,
                             crop=crop,
                             condition=condition,
                             confidence=confidence,
                             theme=theme)
    
    return render_template('disease.html', form=form, theme=theme)

def get_disease_details(condition, crop, confidence):
    """Get detailed information about the detected disease."""
    
    # Handle healthy plants
    if "healthy" in condition.lower():
        return {
            "type": "healthy",
            "description": f"Your {crop} plant appears to be healthy! No disease symptoms detected.",
            "recommendations": [
                "Continue current care practices",
                "Monitor regularly for any changes",
                "Maintain proper watering and nutrition",
                "Ensure good air circulation",
                "Practice preventive measures"
            ],
            "confidence_note": f"Detection confidence: {confidence:.1%}"
        }
    
    # Look for disease information
    disease_info = None
    for disease_key, info in DISEASE_INFO.items():
        if disease_key.lower() in condition.lower() or condition.lower() in disease_key.lower():
            disease_info = info.copy()
            break
    
    # If specific disease not found, provide general information
    if not disease_info:
        disease_info = {
            "description": f"Disease detected in {crop}: {condition}",
            "causes": [
                "Environmental stress factors",
                "Pathogen infection (fungal, bacterial, or viral)",
                "Poor growing conditions",
                "Nutrient imbalances",
                "Inadequate plant care"
            ],
            "symptoms": [
                "Visible signs of disease on plant parts",
                "Reduced plant vigor",
                "Potential yield loss",
                "Quality deterioration"
            ],
            "prevention": [
                "Use disease-resistant varieties",
                "Maintain proper plant spacing",
                "Ensure good air circulation",
                "Practice crop rotation",
                "Remove infected plant debris",
                "Follow integrated pest management"
            ],
            "treatment": [
                "Remove infected plant parts",
                "Apply appropriate fungicides or treatments",
                "Improve growing conditions",
                "Consult local agricultural extension",
                "Consider professional diagnosis"
            ],
            "organic_solutions": [
                "Use organic-approved treatments",
                "Implement cultural control practices",
                "Apply biological control agents",
                "Improve soil health naturally"
            ]
        }
    
    # Add crop-specific information
    disease_info["crop"] = crop
    disease_info["condition"] = condition
    disease_info["confidence"] = confidence
    disease_info["severity_level"] = get_severity_level(condition, confidence)
    disease_info["urgency"] = get_urgency_level(condition, confidence)
    
    return disease_info

def get_severity_level(condition, confidence):
    """Determine severity level based on disease type and confidence."""
    severe_diseases = [
        "late blight", "black rot", "haunglongbing", "citrus greening",
        "yellow leaf curl virus", "mosaic virus", "esca"
    ]
    
    moderate_diseases = [
        "early blight", "bacterial spot", "powdery mildew", "leaf spot",
        "rust", "scab", "leaf blight"
    ]
    
    condition_lower = condition.lower()
    
    if any(disease in condition_lower for disease in severe_diseases):
        if confidence > 0.8:
            return "Critical - Immediate action required"
        else:
            return "High - Prompt treatment needed"
    elif any(disease in condition_lower for disease in moderate_diseases):
        if confidence > 0.7:
            return "Moderate - Treatment recommended"
        else:
            return "Low to Moderate - Monitor closely"
    else:
        return "Monitor and assess"

def get_urgency_level(condition, confidence):
    """Determine urgency of treatment based on disease characteristics."""
    urgent_diseases = [
        "late blight", "haunglongbing", "citrus greening", "black rot",
        "yellow leaf curl virus", "esca"
    ]
    
    condition_lower = condition.lower()
    
    if any(disease in condition_lower for disease in urgent_diseases):
        return "High - Act within 24-48 hours"
    elif "bacterial" in condition_lower or "virus" in condition_lower:
        return "Medium - Act within 3-5 days"
    else:
        return "Low to Medium - Act within 1-2 weeks"

def create_detailed_output(crop, condition, disease_details, confidence):
    """Create a comprehensive output string with disease information."""
    
    if disease_details.get("type") == "healthy":
        return f"""
🌱 **PLANT HEALTH ASSESSMENT**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ **Status:** HEALTHY
🔍 **Crop:** {crop.title()}
📊 **Confidence:** {confidence:.1%}

{disease_details['description']}

**🎯 MAINTENANCE RECOMMENDATIONS:**
{chr(10).join(f"• {rec}" for rec in disease_details['recommendations'])}

Keep up the excellent work! 🌿
        """.strip()
    
    output = f"""
🚨 **PLANT DISEASE DETECTION REPORT**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔍 **Crop:** {crop.title()}
🦠 **Condition:** {condition.title()}
📊 **Confidence:** {confidence:.1%}
⚠️ **Severity:** {disease_details.get('severity_level', 'Assessment needed')}
⏰ **Urgency:** {disease_details.get('urgency', 'Monitor situation')}

**📋 DESCRIPTION:**
{disease_details.get('description', 'Disease information not available.')}

**🔬 PRIMARY CAUSES:**
{chr(10).join(f"• {cause}" for cause in disease_details.get('causes', ['Information not available']))}

**🎯 SYMPTOMS TO MONITOR:**
{chr(10).join(f"• {symptom}" for symptom in disease_details.get('symptoms', ['Information not available']))}

**🛡️ PREVENTION STRATEGIES:**
{chr(10).join(f"• {prevention}" for prevention in disease_details.get('prevention', ['Information not available']))}

**💊 TREATMENT OPTIONS:**
{chr(10).join(f"• {treatment}" for treatment in disease_details.get('treatment', ['Information not available']))}

**🌿 ORGANIC SOLUTIONS:**
{chr(10).join(f"• {organic}" for organic in disease_details.get('organic_solutions', ['Information not available']))}

**⚡ IMMEDIATE ACTION STEPS:**
1. Isolate affected plants if possible
2. Remove and dispose of infected plant parts
3. Improve air circulation around plants
4. Adjust watering practices if needed
5. Apply appropriate treatment based on severity
6. Monitor other plants for similar symptoms

**📞 PROFESSIONAL HELP:**
Consider consulting your local agricultural extension office or plant pathologist for severe cases or if symptoms persist after treatment.

**🔄 FOLLOW-UP:**
Re-assess plant condition in 7-14 days after treatment implementation.
    """.strip()
    
    return output

# Additional utility functions for disease management

def get_seasonal_recommendations(condition, current_month=None):
    """Provide seasonal recommendations for disease management."""
    if not current_month:
        current_month = datetime.now().month
    
    seasonal_advice = {
        "spring": [
            "Apply preventive treatments before disease pressure builds",
            "Clean up overwintered plant debris",
            "Begin regular monitoring as temperatures warm",
            "Ensure proper plant spacing for new plantings"
        ],
        "summer": [
            "Increase monitoring frequency during hot, humid weather",
            "Maintain consistent watering to reduce plant stress",
            "Apply treatments during cooler parts of the day",
            "Provide adequate ventilation in greenhouse settings"
        ],
        "fall": [
            "Clean up infected plant debris before winter",
            "Apply dormant season treatments where appropriate",
            "Plan crop rotations for next season",
            "Prepare preventive strategies for next year"
        ],
        "winter": [
            "Plan disease management strategies for next season",
            "Order resistant varieties and treatments",
            "Clean and disinfect tools and equipment",
            "Study and prepare for common regional diseases"
        ]
    }
    
    if current_month in [3, 4, 5]:
        season = "spring"
    elif current_month in [6, 7, 8]:
        season = "summer"
    elif current_month in [9, 10, 11]:
        season = "fall"
    else:
        season = "winter"
    
    return seasonal_advice[season]

def estimate_treatment_cost(condition, crop, severity="moderate"):
    """Provide rough cost estimates for disease treatment."""
    base_costs = {
        "fungicide": {"low": 15, "moderate": 35, "high": 75},
        "bactericide": {"low": 20, "moderate": 45, "high": 90},
        "organic": {"low": 25, "moderate": 50, "high": 100},
        "biological": {"low": 30, "moderate": 65, "high": 120}
    }
    
    # This is a simplified estimation - actual costs vary greatly
    treatment_type = "fungicide"  # Default
    
    if "bacterial" in condition.lower():
        treatment_type = "bactericide"
    elif "virus" in condition.lower():
        return "Viral diseases require plant removal - no chemical treatment available"
    
    cost_range = base_costs[treatment_type][severity.lower()]
    organic_cost = base_costs["organic"][severity.lower()]
    
    return f"""
💰 **ESTIMATED TREATMENT COSTS (USD per acre):**
• Conventional treatment: ${cost_range-10} - ${cost_range+20}
• Organic treatment: ${organic_cost-15} - ${organic_cost+25}
• Biological control: ${base_costs['biological'][severity.lower()]-20} - ${base_costs['biological'][severity.lower()]+30}

*Note: Costs vary by region, product availability, and application method. 
Consult local suppliers for accurate pricing.*
    """

@app.route('/recommend', methods=['GET', 'POST'])
@login_required
def recommend():
    form = RecommendForm()
    theme = request.args.get('theme', 'bright')
    if form.validate_on_submit():
        inputs = {k: v for k, v in form.data.items() if k not in ['csrf_token', 'submit']}
        output = crop_recommendation(inputs)
        pred = Prediction(user_id=current_user.id, type='recommend', inputs=json.dumps(inputs), output=output)
        db.session.add(pred)
        db.session.commit()
        return render_template('recommend.html', form=form, result=output, theme=theme)
    return render_template('recommend.html', form=form, theme=theme)

fertilizer_dic = {
    # --- Single nutrient issues (6) ---
    "NHigh": """🌱 Excess Nitrogen detected.  
    - Stop/reduce **Urea (IFFCO, KRIBHCO, NFL)** or **DAP (Mosaic, Coromandel)**.  
    - Use organic manure (TrustBasket, Anand Agro Care) instead of synthetic nitrogen.  
    - Consider **slow-release fertilizers** like **Osmocote (ICL, Scotts)**.""",

    "Nlow": """🌱 Nitrogen deficiency.  
    - Apply **Urea (IFFCO, GSFC, NFL)** or **Ammonium Sulphate (RCF, Coromandel)**.  
    - Use **Nano Urea (IFFCO Liquid Urea)** for foliar spray.  
    - Add composted manure or **Vermicompost (Govardhan, TrustBasket)**.""",

    "PHigh": """🌱 Excess Phosphorus detected.  
    - Avoid **DAP (IFFCO, Mosaic)** and **SSP (Coromandel, Paradeep Phosphates)**.  
    - Focus on nitrogen & potassium-only fertilizers.  
    - Use organic matter like compost to balance nutrients.""",

    "Plow": """🌱 Phosphorus deficiency.  
    - Apply **DAP (IFFCO, Mosaic, Coromandel)** or **SSP (Paradeep, Coromandel)**.  
    - Add **Bone Meal (Planters Pride, Local Agri Stores)** or **Rock Phosphate (Fertoz, Bhavnagar Rock)**.  
    - Use P-enriched compost.""",

    "KHigh": """🌱 Excess Potassium detected.  
    - Stop using **MOP (Muriate of Potash - Tata Chemicals, ICL Fertilizers)**.  
    - Avoid **SOP (Sulphate of Potash - Haifa, Compass Minerals)**.  
    - Use gypsum/lime for balance and more organic compost.""",

    "Klow": """🌱 Potassium deficiency.  
    - Apply **MOP (Tata Chemicals, IFFCO)** or **SOP (Haifa, Compass Minerals)**.  
    - Organic: **Banana peels, Wood Ash, Seaweed Fertilizers (Kelpak, Sea6 Energy India)**.""",

    # --- Double nutrient issues (12) ---
    "NHigh_PHigh": """🌱 Excess Nitrogen & Phosphorus.  
    - Avoid **Urea, DAP, SSP**.  
    - Use only **Potash (MOP or SOP - Tata Chemicals, ICL, Haifa)**.  
    - Grow cover crops to absorb excess nutrients.""",

    "NHigh_Plow": """🌱 High Nitrogen, Low Phosphorus.  
    - Reduce urea.  
    - Add **DAP (Coromandel, Mosaic)** or **SSP (Paradeep, Coromandel)**.  
    - Organic: **Bone Meal + Rock Phosphate**.""",

    "NHigh_KHigh": """🌱 Excess Nitrogen & Potassium.  
    - Stop **Urea + MOP/SOP**.  
    - Add phosphorus-only sources like **SSP**.  
    - Focus on organic matter to stabilize soil.""",

    "NHigh_Klow": """🌱 High Nitrogen, Low Potassium.  
    - Reduce urea.  
    - Apply **MOP (Tata, IFFCO)** or **SOP (Haifa)**.  
    - Organic: Seaweed extract + banana compost.""",

    "Nlow_PHigh": """🌱 Low Nitrogen, High Phosphorus.  
    - Add **Urea/Nano Urea (IFFCO)**.  
    - Avoid **DAP/SSP**.  
    - Organic: Vermicompost with high-N plants (beans, peas).""",

    "Nlow_Plow": """🌱 Low Nitrogen & Phosphorus.  
    - Apply **NPK 12:32:16 (IFFCO, Chambal Fertilizers)**.  
    - DAP also works (provides both N & P).  
    - Organic: Vermicompost + Rock Phosphate.""",

    "Nlow_KHigh": """🌱 Low Nitrogen, High Potassium.  
    - Add **Urea (IFFCO, GSFC)**.  
    - Avoid MOP/SOP.  
    - Organic: Nitrogen-fixing crops (legumes).""",

    "Nlow_Klow": """🌱 Low Nitrogen & Potassium.  
    - Use **NPK 15:15:15 (YaraMila Complex, ICL)** or combo of **Urea + MOP**.  
    - Organic: Seaweed fertilizer + manure.""",

    "PHigh_KHigh": """🌱 High Phosphorus & Potassium.  
    - Avoid **DAP, SSP, MOP, SOP**.  
    - Use only nitrogen (Urea, Ammonium Sulphate).  
    - Grow cover crops.""",

    "PHigh_Klow": """🌱 High Phosphorus, Low Potassium.  
    - Avoid DAP/SSP.  
    - Add **MOP (Tata, ICL)** or **SOP (Haifa)**.  
    - Organic: Banana peels, seaweed extract.""",

    "Plow_KHigh": """🌱 Low Phosphorus, High Potassium.  
    - Apply **DAP/SSP**.  
    - Avoid MOP/SOP.  
    - Organic: Bone Meal + Compost.""",

    "Plow_Klow": """🌱 Low Phosphorus & Potassium.  
    - Apply **NPK 10:26:26 (IFFCO, Chambal, Coromandel)**.  
    - Organic: Rock Phosphate + Banana Peel Compost.""",

    # --- Triple nutrient issues (8) ---
    "NHigh_PHigh_KHigh": """🌱 N, P, and K all excessive.  
    - Stop all chemical fertilizers.  
    - Irrigate heavily to leach nutrients.  
    - Grow sorghum/legume cover crops.  
    - Use only organic matter until balance restores.""",

    "NHigh_PHigh_Klow": """🌱 N & P high, K low.  
    - Avoid Urea/DAP.  
    - Add **MOP or SOP (Tata, Haifa, ICL)**.  
    - Organic: Seaweed extract.""",

    "NHigh_Plow_KHigh": """🌱 N high, P low, K high.  
    - Reduce Urea/MOP.  
    - Add **SSP or Rock Phosphate**.  
    - Organic: Bone Meal.""",

    "NHigh_Plow_Klow": """🌱 N high, P & K low.  
    - Reduce Urea.  
    - Add **DAP (Mosaic, Coromandel)** + **MOP (Tata Chemicals)**.  
    - Organic: Compost + Banana peels.""",

    "Nlow_PHigh_KHigh": """🌱 N low, P & K high.  
    - Add **Urea/Nano Urea (IFFCO)**.  
    - Avoid DAP/SSP & MOP/SOP.  
    - Organic: Nitrogen-fixing crops.""",

    "Nlow_PHigh_Klow": """🌱 N low, P high, K low.  
    - Add **Urea + MOP (Tata, ICL)**.  
    - Avoid DAP/SSP.  
    - Organic: Seaweed + manure.""",

    "Nlow_Plow_KHigh": """🌱 N & P low, K high.  
    - Apply **DAP + Urea**.  
    - Reduce MOP/SOP.  
    - Organic: Rock Phosphate + Compost.""",

    "Nlow_Plow_Klow": """🌱 N, P, and K all low.  
    - Apply **NPK 19:19:19 (IFFCO, YaraMila, Haifa Chemicals)**.  
    - Foliar spray with **Water-Soluble NPK 20:20:20 (Haifa, Nova NPK)**.  
    - Organic: Jeevamrut + Panchagavya + Vermicompost."""
}


@app.route('/fertilizer', methods=['GET', 'POST'])
@login_required
def fertilizer():
    form = FertilizerForm()
    theme = request.args.get('theme', 'bright')

    if form.validate_on_submit():
        crop_name = form.cropname.data
        N = form.nitrogen.data
        P = form.phosphorous.data
        K = form.pottasium.data
        ph = form.ph.data
        soil_moisture = form.soil_moisture.data

        import pandas as pd
        from markupsafe import Markup

        # Load recommended values from CSV
        df = pd.read_csv('Data/fertilizer.csv')
        nr = df[df['Crop'] == crop_name]['N'].iloc[0]
        pr = df[df['Crop'] == crop_name]['P'].iloc[0]
        kr = df[df['Crop'] == crop_name]['K'].iloc[0]

        # Calculate differences
        n = nr - N
        p = pr - P
        k = kr - K

        # ✅ Collect all issues instead of just max
        issues = []
        if n != 0:
            issues.append("NHigh" if n < 0 else "Nlow")
        if p != 0:
            issues.append("PHigh" if p < 0 else "Plow")
        if k != 0:
            issues.append("KHigh" if k < 0 else "Klow")

        recs = []

        # ✅ Try to find combined key (e.g. "Nlow_PHigh_Klow")
        key = "_".join(issues)
        if key in fertilizer_dic:
            recs.append(fertilizer_dic[key])
        else:
            # Fallback: use individual recommendations
            for issue in issues:
                if issue in fertilizer_dic:
                    recs.append(fertilizer_dic[issue])

        # ✅ pH check
        if ph < 5.5:
            recs.append(fertilizer_dic.get("pHlow", "Soil is too acidic. Add lime or dolomite."))
        elif ph > 7.5:
            recs.append(fertilizer_dic.get("pHhigh", "Soil is too alkaline. Add gypsum or sulfur."))

        # ✅ Soil moisture check
        if soil_moisture < 30:
            recs.append(fertilizer_dic.get("MoistureLow", "Soil moisture is low. Use drip irrigation or mulching."))
        elif soil_moisture > 70:
            recs.append(fertilizer_dic.get("MoistureHigh", "Soil is too wet. Improve drainage."))

        # ✅ Final response
        response = Markup("<br><br>".join(recs))

        # Save into DB
        pred = Prediction(
            user_id=current_user.id,
            type='fertilizer',
            inputs=json.dumps({
                'crop': crop_name,
                'N': N, 'P': P, 'K': K,
                'pH': ph, 'soil_moisture': soil_moisture
            }),
            output=response
        )
        db.session.add(pred)
        db.session.commit()

        return render_template('fertilizer.html', form=form, recommendation=response, theme=theme)

    return render_template('fertilizer.html', form=form, theme=theme)



@app.route('/price', methods=['GET', 'POST'])
@login_required
def price():
    form = PriceForm()
    theme = request.args.get('theme', 'bright')
    if form.validate_on_submit():
        inputs = {k: v for k, v in form.data.items() if k not in ['csrf_token', 'submit']}
        output = crop_price_prediction(inputs)
        pred = Prediction(user_id=current_user.id, type='price', inputs=json.dumps(inputs), output=output)
        db.session.add(pred)
        db.session.commit()
        return render_template('price.html', form=form, result=output, theme=theme)
    return render_template('price.html', form=form, theme=theme)

@app.route('/health', methods=['GET', 'POST'])
@login_required
def health():
    form = HealthForm()
    theme = request.args.get('theme', 'bright')
    if form.validate_on_submit():
        inputs = {k: v for k, v in form.data.items() if k not in ['csrf_token', 'submit']}
        crop_map = {'Food Crop': 0, 'Cash Crop': 1}
        soil_map = {'Dry': 0, 'Wet': 1}
        pesticide_map = {'Never': 1, 'Previously Used': 2, 'Currently Using': 3}
        season_map = {'Kharif': 1, 'Rabi': 2, 'Zaid': 3}
        inputs['crop_type'] = crop_map[inputs['crop_type']]
        inputs['soil_type'] = soil_map[inputs['soil_type']]
        inputs['pesticide_category'] = pesticide_map[inputs['pesticide_category']]
        inputs['season'] = season_map[inputs['season']]
        output = predict_crop_damage(inputs)
        pred = Prediction(user_id=current_user.id, type='health', inputs=json.dumps(inputs), output=output)
        db.session.add(pred)
        db.session.commit()
        return render_template('health.html', form=form, result=output, theme=theme)
    return render_template('health.html', form=form, theme=theme)

@app.route('/shop', methods=['GET', 'POST'])
@login_required
def shop():
    theme = request.args.get('theme', 'bright')

    # Filter data based on user role
    if current_user.role == Role.FARM_IND:
        # Farm Industry users only see products, not crops
        products = Product.query.all()
        posts = []
    elif current_user.role == Role.COMPANY:
        # Company users only see crops, not products
        posts = CropPost.query.all()
        products = []
    else:
        # Farmers see everything
        posts = CropPost.query.all()
        products = Product.query.all()

    # Handle sending messages
    message_form = MessageForm()
    if message_form.validate_on_submit():
        new_message = Message(
            content=message_form.content.data,
            sender_id=current_user.id,
            receiver_id=request.form.get('receiver_id'),  # dynamically passed from form
            crop_post_id=request.form.get('crop_post_id')  # dynamically passed from form
        )
        db.session.add(new_message)
        db.session.commit()
        flash('Message sent successfully!', 'success')
        return redirect(url_for('shop'))

    return render_template(
        'shop.html',
        posts=posts,
        products=products,
        theme=theme,
        Role=Role,
        message_form=message_form
    )


@app.route('/shop/post', methods=['GET', 'POST'])
@login_required
def shop_post():
    print("Current user role:", current_user.role)  # Debug

    if current_user.role != Role.FARMER:
        flash(_('Only Farmers can post crops'))
        return redirect(url_for('shop'))
    
    form = PostForm()
    theme = request.args.get('theme', 'bright')

    if form.validate_on_submit():
        print("Form validated successfully!")  # Debug
        post = CropPost(
            title=form.title.data,
            description=form.description.data,
            soil_nutrients=form.soil_nutrients.data,
            quality=form.quality.data,
            quantity=form.quantity.data,
            rate=form.rate.data,
            farmer_id=current_user.id
        )
        db.session.add(post)
        db.session.commit()
        print("New CropPost added with ID:", post.id)  # Debug
        flash(_('Crop posted successfully'))
        return redirect(url_for('shop'))
    else:
        print("Form errors:", form.errors)  # Debug
    
    return render_template('shop_post.html', form=form, theme=theme)


@app.route('/shop/product', methods=['GET', 'POST'])
@login_required
def shop_product():
    if current_user.role != Role.FARM_IND:
        flash(_('Only Farm_Ind can post products'))
        return redirect(url_for('shop'))
    form = ProductForm()
    theme = request.args.get('theme', 'bright')
    if form.validate_on_submit():
        product = Product(
            name=form.name.data,
            type=form.type.data,
            description=form.description.data,
            price=form.price.data,
            quantity_available=form.quantity_available.data,
            farm_ind_id=current_user.id
        )
        db.session.add(product)
        db.session.commit()
        flash(_('Product posted successfully'))
        return redirect(url_for('shop'))
    return render_template('shop_product.html', form=form, theme=theme)

@app.route('/shop/query/<int:post_id>', methods=['POST'])
@login_required
def send_query(post_id):
    if current_user.role != Role.COMPANY:
        flash(_('Only Companies can send queries'))
        return redirect(url_for('shop'))
    form = MessageForm()
    if form.validate_on_submit():
        post = CropPost.query.get_or_404(post_id)
        message = Message(
            content=form.content.data,
            sender_id=current_user.id,
            receiver_id=post.farmer_id,
            crop_post_id=post_id
        )
        db.session.add(message)
        db.session.commit()
        flash(_('Query sent'))
    return redirect(url_for('shop'))

@app.route('/shop/purchase/<int:product_id>', methods=['GET', 'POST'])
@login_required
def shop_purchase(product_id):
    if current_user.role != Role.FARMER:
        flash(_('Only Farmers can purchase'))
        return redirect(url_for('shop'))
    form = PurchaseForm()
    product = Product.query.get_or_404(product_id)
    theme = request.args.get('theme', 'bright')
    if form.validate_on_submit():
        if form.quantity.data > product.quantity_available:
            flash(_('Insufficient stock'))
            return render_template('shop_purchase.html', form=form, product=product, theme=theme)
        purchase = Purchase(
            product_id=product_id,
            buyer_id=current_user.id,
            quantity=form.quantity.data,
            total_price=form.quantity.data * product.price
        )
        product.quantity_available -= form.quantity.data
        db.session.add(purchase)
        db.session.commit()
        flash(_('Purchase completed'))
        try:
             charge = stripe.Charge.create(
                 amount=int(purchase.total_price * 100),
                 currency='inr',
                 source=request.form['stripeToken'],
                 description=f'Purchase {product.name}'
             )
             purchase.status = 'Completed'
             db.session.commit()
        except stripe.error.StripeError as e:
             flash(_('Payment failed'))
        return redirect(url_for('shop'))
    return render_template('shop_purchase.html', form=form, product=product, theme=theme)

@app.route('/shop/chat/<int:chat_id>', methods=['GET', 'POST'])
@login_required
def shop_chat(chat_id):
    post = CropPost.query.get_or_404(chat_id)
    messages = Message.query.filter_by(crop_post_id=chat_id).order_by(Message.timestamp).all()
    form = MessageForm()
    theme = request.args.get('theme', 'bright')

    # Allow both Farmer and Company to send messages
    if form.validate_on_submit():
        # Determine the receiver dynamically
        if current_user.role == Role.COMPANY:
            receiver_id = post.farmer_id  # Company sends message to Farmer
        elif current_user.role == Role.FARMER:
            # Farmer sends message to the first company user OR you can pass company_id via form
            company_user = User.query.filter_by(role=Role.COMPANY).first()
            if not company_user:
                flash("No company user available to receive messages.", "danger")
                return redirect(url_for('shop_chat', chat_id=chat_id))
            receiver_id = company_user.id
        else:
            flash("You don't have permission to send messages.", "danger")
            return redirect(url_for('shop_chat', chat_id=chat_id))

        # Create the message
        message = Message(
            content=form.content.data,
            sender_id=current_user.id,
            receiver_id=receiver_id,
            crop_post_id=chat_id
        )
        db.session.add(message)
        db.session.commit()
        flash('Message sent successfully!', 'success')
        return redirect(url_for('shop_chat', chat_id=chat_id))

    return render_template(
        'shop_chat.html',
        messages=messages,
        form=form,
        post=post,
        theme=theme,
        Role=Role
    )


@app.route('/shop/chat/messages/<int:chat_id>')
@login_required
def get_chat_messages(chat_id):
    messages = Message.query.filter_by(crop_post_id=chat_id).order_by(Message.timestamp).all()
    return jsonify([{
        'content': m.content,
        'sender': m.sender.username,
        'timestamp': m.timestamp.isoformat()
    } for m in messages])

# DELETE CropPost (only farmer who created it or admin-like role can delete)
@app.route('/crop_post/delete/<int:post_id>', methods=['POST'])
@login_required
def delete_crop_post(post_id):
    post = CropPost.query.get_or_404(post_id)
    
    if current_user.id != post.farmer_id and current_user.role != Role.COMPANY:
        flash("You are not authorized to delete this crop post.", "danger")
        return redirect(url_for('shop'))  # redirect to shop page or wherever you list posts
    
    db.session.delete(post)
    db.session.commit()
    flash("Crop post removed successfully.", "success")
    return redirect(url_for('shop'))


# DELETE Product (only farm industry owner can delete)
@app.route('/product/delete/<int:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    
    if current_user.id != product.farm_ind_id and current_user.role != Role.FARM_IND:
        flash("You are not authorized to delete this product.", "danger")
        return redirect(url_for('shop'))

    db.session.delete(product)
    db.session.commit()
    flash("Product removed successfully.", "success")
    return redirect(url_for('shop'))


if __name__ == '__main__':
    app.run(debug=True)
