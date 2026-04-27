"""
SevaSetu — Production Seed Data
Realistic humanitarian needs and volunteers across Indian cities.
"""
import asyncio, os, sys, random
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://sevasetu:sevasetu_dev_2024@localhost:5432/sevasetu")

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from app.models.db_models import Base, Need, Volunteer
import hashlib

DB = os.environ["DATABASE_URL"]

NEEDS = [
    # HEALTHCARE — Mumbai
    {"title": "Medical camp needed in Dharavi Ward 5", "description": "Over 150 families in Ward 5 of Dharavi lack access to primary healthcare. Children are showing symptoms of seasonal flu and waterborne diseases. A mobile medical camp with basic medicines, ORS packets, and a pediatrician is urgently required.", "need_type": "HEALTHCARE", "location_name": "Dharavi, Mumbai", "latitude": 19.0422, "longitude": 72.8512, "urgency_base": 0.85, "affected_count": 150, "required_skills": ["nursing", "first_aid", "pediatrics"], "source_channel": "whatsapp", "language": "hi"},
    {"title": "Insulin shortage at Sion Hospital outreach", "description": "The weekly diabetes outreach clinic in Sion reports insulin supply has run out. Approximately 80 diabetic patients from Antop Hill and surrounding areas depend on this facility for their monthly supply.", "need_type": "HEALTHCARE", "location_name": "Sion, Mumbai", "latitude": 19.0400, "longitude": 72.8620, "urgency_base": 0.92, "affected_count": 80, "required_skills": ["pharmacy", "nursing", "diabetes_care"], "source_channel": "google_form", "language": "en"},
    {"title": "Mental health counseling for flood survivors", "description": "Residents of Kurla East who were displaced during last month's flooding are exhibiting signs of PTSD and anxiety. Community leaders have requested trained counselors to conduct group sessions.", "need_type": "HEALTHCARE", "location_name": "Kurla East, Mumbai", "latitude": 19.0726, "longitude": 72.8794, "urgency_base": 0.65, "affected_count": 200, "required_skills": ["counseling", "mental_health", "social_work"], "source_channel": "dashboard", "language": "en"},

    # WATER & SANITATION — Delhi
    {"title": "Borewell repair in Seelampur colony", "description": "The community borewell serving 300+ families in Block D of Seelampur has stopped functioning. Residents have been purchasing water from tankers at Rs 500/week, which most families cannot afford.", "need_type": "WATER_SANITATION", "location_name": "Seelampur, Delhi", "latitude": 28.6598, "longitude": 77.2744, "urgency_base": 0.88, "affected_count": 300, "required_skills": ["plumbing", "borewell_repair"], "source_channel": "whatsapp", "language": "hi"},
    {"title": "Open drain cleanup near Yamuna Pushta", "description": "An open drain running through the Yamuna Pushta resettlement colony has been blocked for two weeks, causing wastewater to overflow into homes. Risk of cholera outbreak reported by local health worker.", "need_type": "WATER_SANITATION", "location_name": "Yamuna Pushta, Delhi", "latitude": 28.6700, "longitude": 77.2400, "urgency_base": 0.90, "affected_count": 450, "required_skills": ["sanitation", "waste_management"], "source_channel": "dashboard", "language": "hi"},
    {"title": "Water purification tablets for Seemapuri", "description": "Groundwater contamination detected in Seemapuri Block 14. Local PHC has reported 25 cases of diarrhea this week. Distribution of water purification tablets and ORS is needed.", "need_type": "WATER_SANITATION", "location_name": "Seemapuri, Delhi", "latitude": 28.6823, "longitude": 77.3123, "urgency_base": 0.82, "affected_count": 180, "required_skills": ["water_purification", "community_health"], "source_channel": "google_form", "language": "en"},

    # FOOD — Kolkata
    {"title": "Mid-day meal gap at Metiabruz primary school", "description": "The government mid-day meal scheme has been suspended at three primary schools in Metiabruz due to a supply chain disruption. 400 children are going without their only guaranteed meal of the day.", "need_type": "FOOD", "location_name": "Metiabruz, Kolkata", "latitude": 22.5140, "longitude": 88.3140, "urgency_base": 0.87, "affected_count": 400, "required_skills": ["cooking", "logistics", "nutrition"], "source_channel": "whatsapp", "language": "bn"},
    {"title": "Ration distribution for Shyamnagar flood victims", "description": "Families displaced by Hooghly river flooding in Shyamnagar need dry ration kits including rice, dal, oil, and salt. An estimated 120 families are currently sheltered at the local community hall.", "need_type": "FOOD", "location_name": "Shyamnagar, Kolkata", "latitude": 22.8300, "longitude": 88.3700, "urgency_base": 0.80, "affected_count": 120, "required_skills": ["logistics", "community_outreach"], "source_channel": "dashboard", "language": "bn"},
    {"title": "Community kitchen setup in Park Circus", "description": "Daily wage workers in Park Circus have lost income due to construction site closures. Around 60 families need cooked meals for the next two weeks until work resumes.", "need_type": "FOOD", "location_name": "Park Circus, Kolkata", "latitude": 22.5388, "longitude": 88.3622, "urgency_base": 0.70, "affected_count": 60, "required_skills": ["cooking", "food_safety"], "source_channel": "whatsapp", "language": "hi"},

    # SHELTER — Chennai
    {"title": "Temporary shelter for evicted families in Perumbakkam", "description": "32 families evicted from unauthorized settlements along the Adyar river need immediate temporary shelter. Women and children are currently sleeping in the open near the bus terminal.", "need_type": "SHELTER", "location_name": "Perumbakkam, Chennai", "latitude": 12.9060, "longitude": 80.2000, "urgency_base": 0.93, "affected_count": 32, "required_skills": ["construction", "tarpaulin_setup", "social_work"], "source_channel": "dashboard", "language": "ta"},
    {"title": "Roof repair after cyclone damage in Ennore", "description": "Cyclone Michaung damaged roofs of 45 houses in the fishing hamlet near Ennore creek. Families are using plastic sheets but monsoon rains are expected in 10 days.", "need_type": "SHELTER", "location_name": "Ennore, Chennai", "latitude": 13.2164, "longitude": 80.3222, "urgency_base": 0.78, "affected_count": 45, "required_skills": ["construction", "roofing", "carpentry"], "source_channel": "google_form", "language": "ta"},

    # EDUCATION — Pune
    {"title": "After-school tutoring for migrant children in Hadapsar", "description": "Children of sugarcane-cutting migrant workers in Hadapsar have missed 3 months of school. 65 children aged 6-14 need intensive bridge education to rejoin their grade-appropriate classes.", "need_type": "EDUCATION", "location_name": "Hadapsar, Pune", "latitude": 18.5100, "longitude": 73.9300, "urgency_base": 0.60, "affected_count": 65, "required_skills": ["teaching", "marathi", "hindi"], "source_channel": "dashboard", "language": "mr"},
    {"title": "Digital literacy workshop in Kothrud slum", "description": "A self-help group of 40 women in Kothrud has requested digital literacy training to access government welfare schemes through smartphones. Most are first-generation smartphone users.", "need_type": "EDUCATION", "location_name": "Kothrud, Pune", "latitude": 18.5074, "longitude": 73.8077, "urgency_base": 0.45, "affected_count": 40, "required_skills": ["digital_literacy", "teaching", "marathi"], "source_channel": "google_form", "language": "mr"},

    # INFRASTRUCTURE — across cities
    {"title": "Broken street lights in Govandi East", "description": "12 street lights along the main road in Govandi East have been non-functional for 6 weeks. Women and elderly residents report feeling unsafe commuting after dark. BMC complaint filed but no action taken.", "need_type": "INFRASTRUCTURE", "location_name": "Govandi, Mumbai", "latitude": 19.0627, "longitude": 72.9270, "urgency_base": 0.55, "affected_count": 500, "required_skills": ["electrical", "municipal_liaison"], "source_channel": "whatsapp", "language": "hi"},
    {"title": "Collapsed pedestrian bridge near Elphinstone station", "description": "The foot overbridge connecting Elphinstone Road station to the western side has developed dangerous cracks. Commuters are using an alternate longer route, causing overcrowding during peak hours.", "need_type": "INFRASTRUCTURE", "location_name": "Elphinstone, Mumbai", "latitude": 19.0000, "longitude": 72.8400, "urgency_base": 0.75, "affected_count": 2000, "required_skills": ["structural_engineering", "safety_audit"], "source_channel": "dashboard", "language": "en"},

    # LIVELIHOOD
    {"title": "Sewing machines for women's cooperative in Dharavi", "description": "A women's self-help group in Dharavi Transit Camp has 25 trained tailors but only 4 working sewing machines. Providing refurbished machines would help them earn Rs 8000-12000 per month.", "need_type": "LIVELIHOOD", "location_name": "Dharavi, Mumbai", "latitude": 19.0450, "longitude": 72.8550, "urgency_base": 0.50, "affected_count": 25, "required_skills": ["livelihood_training", "microfinance"], "source_channel": "google_form", "language": "hi"},
    {"title": "Fishing net repair kits for Versova koliwada", "description": "Monsoon storms destroyed fishing nets for 30 families in Versova koliwada. Without nets, these families have no income. Basic repair kits with nylon thread and needles are needed.", "need_type": "LIVELIHOOD", "location_name": "Versova, Mumbai", "latitude": 19.1390, "longitude": 72.8120, "urgency_base": 0.72, "affected_count": 30, "required_skills": ["fishing", "logistics"], "source_channel": "whatsapp", "language": "mr"},

    # More realistic needs across cities
    {"title": "Wheelchair ramp for Andheri community center", "description": "The Andheri East community center serves 15 elderly and disabled residents who cannot access the first-floor meeting hall. A concrete wheelchair ramp with handrails is needed.", "need_type": "INFRASTRUCTURE", "location_name": "Andheri East, Mumbai", "latitude": 19.1136, "longitude": 72.8697, "urgency_base": 0.48, "affected_count": 15, "required_skills": ["construction", "accessibility_design"], "source_channel": "dashboard", "language": "en"},
    {"title": "Vaccination drive for construction site workers", "description": "Construction workers at the Bandra-Worli Sea Link extension site have not received tetanus or hepatitis B vaccinations. The site employs 250 migrant workers from Bihar and UP.", "need_type": "HEALTHCARE", "location_name": "Bandra, Mumbai", "latitude": 19.0500, "longitude": 72.8260, "urgency_base": 0.68, "affected_count": 250, "required_skills": ["nursing", "vaccination", "first_aid"], "source_channel": "dashboard", "language": "hi"},
    {"title": "Emergency water tanker for Malad hill settlement", "description": "Pipeline burst in Malad West has cut water supply to an informal settlement of 200 families on the hillside. Municipal repair estimated at 5 days. Immediate water tanker service required.", "need_type": "WATER_SANITATION", "location_name": "Malad West, Mumbai", "latitude": 19.1860, "longitude": 72.8320, "urgency_base": 0.91, "affected_count": 200, "required_skills": ["logistics", "water_distribution"], "source_channel": "whatsapp", "language": "hi"},
    {"title": "School uniform donation for Thane orphanage", "description": "Bal Kalyan orphanage in Thane houses 48 children. New academic year starting in June and 35 children need school uniforms, shoes, and bags. Sizes range from age 5-15.", "need_type": "EDUCATION", "location_name": "Thane, Mumbai", "latitude": 19.2183, "longitude": 72.9781, "urgency_base": 0.40, "affected_count": 35, "required_skills": ["logistics", "community_outreach"], "source_channel": "google_form", "language": "mr"},
    {"title": "Toilet block construction in Govindpuri JJ colony", "description": "450 families in Govindpuri JJ cluster share only 6 functional community toilets. Women report safety concerns using facilities after dark. Construction of an 8-seat toilet block with lighting is needed.", "need_type": "WATER_SANITATION", "location_name": "Govindpuri, Delhi", "latitude": 28.5372, "longitude": 77.2498, "urgency_base": 0.76, "affected_count": 450, "required_skills": ["construction", "plumbing", "sanitation"], "source_channel": "dashboard", "language": "hi"},
    {"title": "Free legal aid camp for domestic workers in Noida", "description": "Domestic workers' union in Noida Sector 62 has reported 15 cases of wage theft. Workers need legal guidance on labor laws and help filing complaints with the labor commissioner.", "need_type": "LIVELIHOOD", "location_name": "Noida, UP", "latitude": 28.6270, "longitude": 77.3650, "urgency_base": 0.55, "affected_count": 15, "required_skills": ["legal_aid", "labor_law", "hindi"], "source_channel": "whatsapp", "language": "hi"},
    {"title": "Mosquito net distribution in Patna flood zone", "description": "Stagnant floodwater in Rajiv Nagar, Patna has caused a surge in dengue cases. 180 families need insecticide-treated mosquito nets before the situation worsens.", "need_type": "HEALTHCARE", "location_name": "Rajiv Nagar, Patna", "latitude": 25.5941, "longitude": 85.1376, "urgency_base": 0.83, "affected_count": 180, "required_skills": ["community_health", "logistics", "first_aid"], "source_channel": "dashboard", "language": "hi"},
    {"title": "Solar lanterns for Sundarbans village", "description": "Gosaba island in Sundarbans has had no electricity for 3 weeks after storm damage to the micro-grid. 90 families need solar lanterns for basic lighting, especially for children studying at night.", "need_type": "INFRASTRUCTURE", "location_name": "Gosaba, Sundarbans", "latitude": 22.1650, "longitude": 88.8060, "urgency_base": 0.67, "affected_count": 90, "required_skills": ["solar_installation", "electrical", "logistics"], "source_channel": "whatsapp", "language": "bn"},
    {"title": "Physiotherapy sessions for accident survivors in Dadar", "description": "A local NGO supporting road accident survivors has 22 patients needing regular physiotherapy. The nearest government facility has a 3-month waitlist. Volunteer physiotherapists are needed.", "need_type": "HEALTHCARE", "location_name": "Dadar, Mumbai", "latitude": 19.0178, "longitude": 72.8478, "urgency_base": 0.58, "affected_count": 22, "required_skills": ["physiotherapy", "rehabilitation"], "source_channel": "dashboard", "language": "en"},
    {"title": "Emergency food packets for stranded train passengers", "description": "Heavy rains have halted train services at Kalyan junction. An estimated 500 passengers including elderly and children have been stranded for 8 hours with no food available at the station.", "need_type": "FOOD", "location_name": "Kalyan, Mumbai", "latitude": 19.2437, "longitude": 73.1355, "urgency_base": 0.95, "affected_count": 500, "required_skills": ["cooking", "logistics", "crowd_management"], "source_channel": "whatsapp", "language": "hi"},
]

VOLUNTEERS = [
    {"name": "Dr. Priya Sharma", "phone": "+919876543201", "skills": ["nursing", "first_aid", "pediatrics", "vaccination"], "languages": ["hindi", "english", "marathi"], "latitude": 19.0760, "longitude": 72.8777, "has_vehicle": True, "vehicle_type": "four_wheeler", "experience_text": "MBBS from Grant Medical College. 5 years at KEM Hospital. Active volunteer with Mercy Foundation for community health camps."},
    {"name": "Rajesh Patil", "phone": "+919876543202", "skills": ["plumbing", "borewell_repair", "construction"], "languages": ["hindi", "marathi"], "latitude": 19.0500, "longitude": 72.8800, "has_vehicle": True, "vehicle_type": "two_wheeler", "experience_text": "Licensed plumber with 12 years experience. Previously worked on BMC water supply projects in M-East ward."},
    {"name": "Amina Sheikh", "phone": "+919876543203", "skills": ["teaching", "digital_literacy", "counseling"], "languages": ["hindi", "english", "urdu"], "latitude": 19.0330, "longitude": 72.8450, "has_vehicle": False, "experience_text": "B.Ed graduate. Runs after-school tuition for slum children in Bandra. Trained in child psychology."},
    {"name": "Suresh Kumar", "phone": "+919876543204", "skills": ["cooking", "food_safety", "logistics"], "languages": ["hindi", "bhojpuri"], "latitude": 19.0700, "longitude": 72.8900, "has_vehicle": True, "vehicle_type": "three_wheeler", "experience_text": "Former mess contractor for L&T construction sites. Can cook for 200+ people. Food handling certified."},
    {"name": "Fatima Begum", "phone": "+919876543205", "skills": ["social_work", "community_outreach", "counseling", "mental_health"], "languages": ["hindi", "english", "bengali"], "latitude": 22.5500, "longitude": 88.3400, "has_vehicle": False, "experience_text": "MSW from Jadavpur University. 4 years at CINI working on child nutrition programs in urban slums."},
    {"name": "Vikram Singh", "phone": "+919876543206", "skills": ["construction", "roofing", "carpentry", "tarpaulin_setup"], "languages": ["hindi", "english"], "latitude": 28.6500, "longitude": 77.2300, "has_vehicle": True, "vehicle_type": "four_wheeler", "experience_text": "Civil engineer, 8 years in affordable housing projects. Volunteer with Habitat for Humanity India."},
    {"name": "Lakshmi Devi", "phone": "+919876543207", "skills": ["nursing", "community_health", "first_aid", "diabetes_care"], "languages": ["tamil", "english"], "latitude": 13.0400, "longitude": 80.2400, "has_vehicle": True, "vehicle_type": "two_wheeler", "experience_text": "Auxiliary Nurse Midwife. 10 years in Chennai Corporation health centers. Trained ASHA worker mentor."},
    {"name": "Mohammed Irfan", "phone": "+919876543208", "skills": ["logistics", "crowd_management", "water_distribution"], "languages": ["hindi", "urdu", "english"], "latitude": 19.1200, "longitude": 72.8500, "has_vehicle": True, "vehicle_type": "four_wheeler", "experience_text": "Ex-Army logistics corps. 6 years of disaster relief experience with NDRF volunteer wing."},
    {"name": "Sneha Desai", "phone": "+919876543209", "skills": ["legal_aid", "labor_law", "social_work"], "languages": ["hindi", "english", "gujarati"], "latitude": 19.0200, "longitude": 72.8300, "has_vehicle": False, "experience_text": "Practicing advocate at Mumbai High Court. Pro-bono work for domestic workers and construction laborers."},
    {"name": "Arjun Nair", "phone": "+919876543210", "skills": ["electrical", "solar_installation", "municipal_liaison"], "languages": ["hindi", "english", "malayalam"], "latitude": 19.1100, "longitude": 72.8600, "has_vehicle": True, "vehicle_type": "two_wheeler", "experience_text": "Certified electrician with NSDC. Installed solar panels in 50+ rural homes with Barefoot College alumni network."},
    {"name": "Kavita Rao", "phone": "+919876543211", "skills": ["nutrition", "cooking", "community_health"], "languages": ["hindi", "marathi", "kannada"], "latitude": 18.5200, "longitude": 73.8600, "has_vehicle": False, "experience_text": "Dietician with B.Sc in Food Science. Runs a community kitchen for migrant workers in Pune every weekend."},
    {"name": "Ravi Shankar", "phone": "+919876543212", "skills": ["sanitation", "waste_management", "plumbing"], "languages": ["hindi", "english"], "latitude": 28.6800, "longitude": 77.3000, "has_vehicle": True, "vehicle_type": "two_wheeler", "experience_text": "Worked with Sulabh International for 7 years on community toilet construction across UP and Delhi."},
    {"name": "Deepa Mukherjee", "phone": "+919876543213", "skills": ["teaching", "counseling", "marathi", "bengali"], "languages": ["bengali", "hindi", "english"], "latitude": 22.5700, "longitude": 88.3600, "has_vehicle": False, "experience_text": "Retired school principal. Volunteers 3 days a week teaching English and Math at railway children's shelter."},
    {"name": "Anand Tiwari", "phone": "+919876543214", "skills": ["structural_engineering", "safety_audit", "construction"], "languages": ["hindi", "english"], "latitude": 19.0050, "longitude": 72.8350, "has_vehicle": True, "vehicle_type": "four_wheeler", "experience_text": "Structural engineer at Larsen & Toubro. Certified building safety auditor. Volunteers for post-disaster assessments."},
    {"name": "Meera Krishnan", "phone": "+919876543215", "skills": ["physiotherapy", "rehabilitation", "first_aid"], "languages": ["tamil", "english", "hindi"], "latitude": 13.0800, "longitude": 80.2700, "has_vehicle": True, "vehicle_type": "two_wheeler", "experience_text": "MPT in Orthopedics from CMC Vellore. 3 years at Apollo Hospital. Runs free physio camp monthly in Tambaram."},
    {"name": "Salim Khan", "phone": "+919876543216", "skills": ["logistics", "fishing", "community_outreach"], "languages": ["hindi", "marathi"], "latitude": 19.1400, "longitude": 72.8100, "has_vehicle": True, "vehicle_type": "two_wheeler", "experience_text": "Versova koliwada fisherman leader. Coordinates disaster response for 200 fishing families along Juhu coast."},
    {"name": "Pooja Gupta", "phone": "+919876543217", "skills": ["pharmacy", "nursing", "water_purification"], "languages": ["hindi", "english"], "latitude": 28.6600, "longitude": 77.2800, "has_vehicle": False, "experience_text": "B.Pharm from Delhi University. Manages a Jan Aushadhi Kendra. Trained in water quality testing by UNICEF."},
    {"name": "Thomas Joseph", "phone": "+919876543218", "skills": ["livelihood_training", "microfinance", "digital_literacy"], "languages": ["english", "hindi", "malayalam"], "latitude": 19.0600, "longitude": 72.8360, "has_vehicle": False, "experience_text": "Former NABARD officer. Now runs SHG federation supporting 1200 women across Mumbai's M-ward."},
    {"name": "Geeta Devi", "phone": "+919876543219", "skills": ["community_outreach", "hindi", "cooking"], "languages": ["hindi", "bhojpuri"], "latitude": 25.6000, "longitude": 85.1400, "has_vehicle": False, "experience_text": "Anganwadi worker for 15 years in Patna. Knows every family in Rajiv Nagar. Trained in malnutrition screening."},
    {"name": "Sanjay Mestry", "phone": "+919876543220", "skills": ["construction", "accessibility_design", "carpentry"], "languages": ["hindi", "marathi", "english"], "latitude": 19.1150, "longitude": 72.8700, "has_vehicle": True, "vehicle_type": "four_wheeler", "experience_text": "Contractor specializing in accessible infrastructure. Built ramps at 12 BMC schools under Sarva Shiksha Abhiyan."},
]


def _hash(desc):
    return hashlib.sha256(desc.strip().lower().encode()).hexdigest()


async def main():
    engine = create_async_engine(DB, echo=False)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE assignments, needs, volunteers RESTART IDENTITY CASCADE"))
    print("✅ Cleared all existing data")

    async with Session() as session:
        now = datetime.utcnow()

        # Seed needs with staggered created_at times
        for i, n in enumerate(NEEDS):
            hours_ago = random.uniform(1, 72)
            need = Need(
                title=n["title"],
                description=n["description"],
                need_type=n["need_type"],
                location_name=n["location_name"],
                latitude=n["latitude"],
                longitude=n["longitude"],
                urgency_base=n["urgency_base"],
                urgency_current=min(1.0, n["urgency_base"] + random.uniform(0, 0.08)),
                affected_count=n["affected_count"],
                required_skills=n["required_skills"],
                status=random.choice(["new", "new", "new", "matched", "assigned"]),
                source_channel=n["source_channel"],
                language=n.get("language"),
                content_hash=_hash(n["description"]),
                created_at=now - timedelta(hours=hours_ago),
            )
            session.add(need)

        # Seed volunteers
        for v in VOLUNTEERS:
            vol = Volunteer(
                name=v["name"],
                phone=v["phone"],
                skills=v["skills"],
                languages=v["languages"],
                latitude=v["latitude"],
                longitude=v["longitude"],
                has_vehicle=v["has_vehicle"],
                vehicle_type=v.get("vehicle_type"),
                experience_text=v["experience_text"],
                reliability=round(random.uniform(0.65, 0.95), 2),
                total_tasks=random.randint(3, 20),
                completed_tasks=random.randint(2, 15),
                status="available",
            )
            session.add(vol)

        await session.commit()
        print(f"✅ Seeded {len(NEEDS)} needs and {len(VOLUNTEERS)} volunteers")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
