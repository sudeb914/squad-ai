"""Built-in defaults seeded on first run.

The app ships with a default instruction (system) prompt and a default
reference/training corpus so it works out of the box. These are seeded only when
the user hasn't set their own (see Services._seed_defaults) — the user can edit
or clear them anytime in Settings, and their changes are never overwritten.
"""
from __future__ import annotations

# Default instruction prompt (sent as the user's custom instruction to the AI).
DEFAULT_SYSTEM_PROMPT = (
    "তুমি একজন প্রোফাইল-ভিত্তিক সার্ভে উত্তর সহকারী হিসেবে কাজ করবে।\n"
    "আমি তোমাকে কিছু ডাটা প্রদান করব, যেখানে থাকবে একটি নির্দিষ্ট প্রোফাইলের তথ্য, "
    "পূর্বের সার্ভে প্রশ্ন এবং সেই প্রশ্নগুলোর উত্তর। তোমার কাজ হবে এই ডাটাগুলো "
    "বিশ্লেষণ করে প্রোফাইলের বৈশিষ্ট্য, পছন্দ, অভ্যাস এবং পূর্বের উত্তর দেওয়ার ধরন "
    "বুঝে নেওয়া।\n"
    "ডাটা বিশ্লেষণ করার পর তুমি একটি অভ্যন্তরীণ প্রোফাইল তৈরি করবে। পরবর্তীতে আমি "
    "যখন নতুন কোনো সার্ভে সেশন, প্রশ্ন বা প্রশ্নের সেট প্রদান করব, তখন তোমাকে সেই "
    "প্রশ্নগুলো বিশ্লেষণ করে পূর্বে শেখা প্রোফাইলের সাথে মিল রেখে সবচেয়ে উপযুক্ত উত্তর "
    "দিতে হবে।\n"
    "তোমার উত্তর দেওয়ার নিয়মগুলো:\n"
    "১. সবসময় আগে দেওয়া প্রোফাইল ডাটাকে প্রাধান্য দিতে হবে।\n"
    "২. নতুন কোনো প্রশ্ন যদি প্রোফাইলের সাথে সম্পর্কিত হয়, তাহলে এমন উত্তর দিতে হবে যা "
    "সেই প্রোফাইলের সাথে স্বাভাবিকভাবে মিলে যায়।\n"
    "৩. নিজের থেকে কোনো কাল্পনিক বা অপ্রাসঙ্গিক তথ্য তৈরি করা যাবে না।\n"
    "৪. প্রয়োজন ছাড়া কোনো ব্যাখ্যা, কারণ বা অতিরিক্ত তথ্য যোগ করা যাবে না।\n"
    "৫. সার্ভে প্রশ্নের জন্য শুধুমাত্র প্রয়োজনীয় চূড়ান্ত উত্তর প্রদান করবে।\n"
    "৬. পূর্বের ডাটায় যেভাবে উত্তর দেওয়া হয়েছে, সেই একই ধরন ও ধারাবাহিকতা বজায় "
    "রাখবে।\n"
    "৭. যদি কোনো প্রশ্নের একাধিক সম্ভাব্য উত্তর থাকে, তাহলে যে উত্তরটি পূর্বের প্রোফাইল "
    "এবং উত্তর দেওয়ার প্যাটার্নের সাথে সবচেয়ে বেশি সামঞ্জস্যপূর্ণ সেটি নির্বাচন করবে।\n"
    "৮. আমি যখন নতুন কোনো সেশন বা অতিরিক্ত ডাটা প্রদান করব, তখন সেই তথ্য ব্যবহার "
    "করে তোমার প্রোফাইল বোঝার ক্ষমতা আপডেট করবে।\n"
    "তোমার মূল লক্ষ্য হলো দেওয়া তথ্যের ভিত্তিতে একটি নির্দিষ্ট ব্যবহারকারীর প্রোফাইল "
    "ধারাবাহিকভাবে অনুসরণ করা এবং প্রতিটি নতুন সার্ভে প্রশ্নের জন্য সেই প্রোফাইলের সাথে "
    "সামঞ্জস্যপূর্ণ, নির্ভুল এবং মানসম্মত উত্তর প্রদান করা।"
)

# Default reference / training corpus (the user's curated survey answer key).
DEFAULT_REFERENCE = r"""Race : White / Caucasian
Ethnicity : Not hispanic/latino/spanish
Gender : Male
Sexual orientation : Heterosexual / Straight
Religion: Christian / Protestant
Home : Own / Single Family Home / Town House
Bought/lease home : New
Type of Area live in: Urban
Family member : 4 person (including yourself)
Pets: 1 Dog & 1 Cat & 1 Bird
Dog Name & Breed: Hulk, German Shepherd
Cat Name & Breed: Tom, Napoleon cat
Bird Name & Breed: Bella, Grey parrot
Job Type : Full time (30+ Hours per week)
Occupation : Information Technology or IT / Computer Software
Post : Manager / Senior manager
Child interest in work: yes (always)
Income (annual) : 150,000 (same for US/UK/Germany)
Income (per month) : 12,500
Total Wealth/Equity : 1 Million
Total employee (company): 1000-2500 person
Education : Professional degree or Masters Degree & Post Graduate Degree
Decision Takers : Myself (all sections)
Company revenue : 25-50 Million Dollars

Do you or anyone in your household work in any of the following industries? Information Technology/IT
Which department do you primarily work within at your organization? Technology Development Software (not only IT)
Departments/products you have influence or decision making authority over: IT Hardware, IT Software
Please estimate your annual household income before/pre tax: 150,000
Which best describes the industry your company operates in? IT or computer software services.
Job title : Manager / General Manager / HR Manager
What is your estimated financial worth? 1 Million+
Approximate estimated home value? 500,000-700,000
Diagnosed illnesses/conditions: Depression, Anxiety, Back Pain, Diabetes
Issuer of your primary credit card: Bank of America
Financial/insurance products you have: Health Insurance, Auto Insurance
Primary mobile phone plan: Individual plan (Prepaid)
What industry do you work in? Science and Technology (only if IT is not present)
Gaming platforms you regularly use: iPad, iPhone, PC/Desktop/laptop/Mac, Nintendo Switch, PlayStation 5, Steam Deck, VR devices (Oculus Quest, HTC Vive), Xbox Series X/S
Primary Bank: Bank of America
Areas of company involved in purchase decision: IT or computer hardware, IT or computer software
Additional health insurance: UnitedHealthcare
Primary health insurance company: Kaiser Permanente
How often do you go to the movie theater? 1-3 times per month
Approximate annual revenue for your organization: 10 Million to 24.99 million
Would you describe the area you live in as? Urban
When you fly, which types of flights do you take? Both domestic and international
Occupation of chief income earner in household: Higher managerial, administrative and professional
IT roles/functions you operate within: IT Services Sourcing Manager
Military background? No / I have no military background
Device: Samsung/Apple (use latest brand/model)
Use phone: 4-5 hours/day or 25-30 hours per week
TV Cable: Satellite
Online shopped: More than 12 times+ per month
Regular visit: Computer & electronics
Streaming services: Netflix, Amazon Prime, Hulu, Paramount, Apple TV+, Peacock
Social media platforms: Facebook, Instagram, LinkedIn, YouTube, Twitter, Snapchat
Insurance: Home/Property Mortgage or loan, Health Insurance, Auto/Car loans
Credit Card: Mastercard / American Express
Loans: Credit Card Loan, Auto/car loan, Mortgage loan
Investment Products: Shares/Stocks/Bonds/Saving for Pension/IRA
Banks used: Bank of America, U.S. Bank, Wells Fargo
Bank Account types: Savings, Checking, Investment
Payments: PayPal, Venmo, Cash App, Google Pay, Mobile Banking, Credit card, Cash
Registered to vote? Yes
Political Party: Republican / Conservative
Vehicles: 2 (1 Car, 1 Motorcycle)
Buy/lease vehicle new or used? Always New
Car: BMW X5, Model Year 2017, bought 2018, Midsize luxury SUV, bought new with cash and auto loan
Motorcycle: Harley-Davidson Fat Boy, Model Year 2022, bought new 2023
Next vehicle purchase: 6-12 months / 1 year
Company type: For-Profit / Private Business
Industry/age of company: up to 20 years; worked in this industry for 15 years
Company offers: IT services + IT Software
Current job type: Technology Development Software (not only IT)
Store/grocery visited: Walmart, Target (4-6 times per week)
Restaurants: KFC, Starbucks, McDonald's, Pizza Hut, Chipotle, Burger King, Wendy's, Taco Bell (4-6 times per week)
Online stores: eBay, Amazon (4-6 times per week)
Ride sharing / delivery: Uber, Uber Eats, DoorDash, Lyft, Grab
Games: FPS, Racing, RPG, Action, Adventure, Story-driven, Exploration
Devices for gaming: iPhone, iPad, PC, Xbox Series X, PlayStation 5, Steam Deck, VR, Nintendo Switch
Hours playing video games: 12-14 hours per week (offline & online)
Hobbies: Playing video games, Camping, Swimming, Biking, Photography, Painting, Yoga, Gym, Coding/Programming, Electronics, Computers
Sports participated locally: golf, basketball, tennis (never attend events)
Watch TV: yes (14 hours per week) — Football, Soccer, Baseball, Basketball, Golf, Sports Car/Bike racing
Bet/Gamble? Yes
TV Channels: CNN, BBC, National Geographic, Discovery Channel, TLC
Stream movies: yes (14-16 hours/week) — Documentary, Action, Horror, Drama, Series
Movies in theater: 1-3 times per month
Magazines: Both online and offline (4-6 hours per week)
Newspapers: USA Today, New York Times (online and offline)
Radio: 4-5 hours per week
Podcasts: 8-10 hours per week
Travel/Fly: Domestic and International; Domestic 16-20 times/year, International 12-14 times/year
Hotels: 4 Star and 5 Star; makes all travel decisions
Race/Ethnicity: White/Caucasian, Not Hispanic
Primary decision maker in everything: Yes (I make all decisions)
Connected/smart TV devices: Google TV/Android TV, Amazon Fire TV Stick/Cube
Intend to buy new gaming console in next 12 months: Yes (Nintendo Switch, PlayStation 5)
Health apps used: routine apps, fitness apps, medication checkers/reminders
Watch live streams? Both live and pre-recorded
Drinks consumed in past 4 weeks: Beer, Wine, Energy drinks, Coffee, Tea, Carbonated soft drinks, Fruit juices, Bottled water
Stores shopped past 6 months: Auto supply/service, Computer & home electronics, Discount (Walmart, Target), Drug stores, Hardware/Home supply, Natural/Organic, Office supplies, Online-only retailers, Online grocers, Specialty clothing, Supercenter (Super Target), Toys/Children's
Pizza restaurants visited every 3 months: Pizza Hut, Domino's Pizza
Estimated financial worth: 2 Million
Tobacco products past 30 days: Large/little cigars or cigarillos, E-cigarettes/vapor, Tobacco cigarettes
Political view: Republican (Conservative)
Facial skin care used daily: Day Cream, Moisturizer, Night Cream, Sunscreen
Annual revenue of company: 25 million (or 10-25 million)
Communication/collaboration tools heard of: Gmail, Cisco WebEx Teams, Slack, Microsoft Outlook
Household spend on exercise/gym/fitness: 450-599$
Job title: General Manager
Vehicle repair location: Local/garage mechanic
Gender identity: Heterosexual/Straight/Male
Vaccinated for COVID-19? Yes (February 2021)
Small business owner or manager? No (I do a job for a private company)
Fan of professional sports: Basketball, Soccer
Purchases using: Google Pay, PayPal, Venmo
Mobile game genres: Battle Royale (Fortnite, COD Mobile, PUBG Mobile), Casual (Candy Crush, Homescapes), Sports/Racing (FIFA, CSR Racing), Card/Gambling (Solitaire, Coin Master), Casual strategy (Clash of Clans)
Workplace: Work from office most of the time but sometimes from home
Bought in past 2 years: TV, Computer, Smartphone, Video Game System
Prayer/church: Every week (4 times a month)
Gun ownership: Yes (I own a gun)
Products purchased past 6 months: Cooking oils, Personal wash products
Products past 3 months personal use: Razors, Facial cleansing products, Hair care, Body wash, Body care
News sources online past 30 days: Fox News, The New York Times, CNN
Smart/connected devices owned: Connected exercise equipment (Peloton, Tonal), Smart speakers (Alexa, Google Assistant), Smart watches (Apple Watch, Fitbit), Home security (Vivint, SimpliSafe)
Spent on smart devices past 12 months: 1000$-2499$
Phone lines on wireless plan: 1 (individual)
Wireless data: unlimited data plan
Home landline: No
Federal assistance eligibility: None
Personal brokerage/retirement account (IRA etc): Yes
Employer-sponsored retirement plan (401k/403b): Yes
Retirement account types: 401(k), 403(b), 457
401k/403b provider: Bank of America
Purchased past 12 months: jeans, street/fashion/lifestyle apparel, dress shoes, dress shirt
Purchased brand new for home past 3 years: Side-by-side refrigerator
Dog coat: Medium haired (German Shepherd), Double Coat
Driver's license: Yes
Managing diabetes: Taking insulin injections; diagnosed with type 1 diabetes 1-2 years ago; only I have diabetes in the family
Supporter/ally of LGBTQ community: No
Estimated home/property value: 500,000-700,000
Job title/position: Intermediate managerial (Director)
Company type worked for: A private / for-profit company or organisation
Loans: Automobile loan, Mortgage (from Bank of America)
Razor for facial hair: Electric razor; razor blades: 3
Shoe brands open to: Adidas, Nike, Skechers
Willing to spend on shoes: 101-150
Digital fitness apps: Nike Training/Run Club, MyFitnessPal
Open to purchase: Both vegan and non-vegan products
Occupation: Information Technology/IT (not Telecommunications)
Satellite/Cable TV provider: DirecTV / DirecTV Now
Food statements: I don't eat animal products (meaning cat/dog food); I prefer organic food products
Credit score: Exceptional (800-850)
Financial products currently have: Credit Card, Savings/High Earnings Account, Loan
iPhone: iPhone 15 (bought October 2023, 6.1-inch, $799)
Involvement in telecommunication services: I am not involved
Average saved in banking accounts: $400,000 to $449,999
Wireless providers with data plan: AT&T, T-Mobile
Home internet / broadband provider: AT&T (5 years or longer); receive discounts directly from ISP; discount not related to profession
8-year-old girl watches TV: 16-20 hours; channels: Nickelodeon, Cartoon Network, Disney Channel, Discovery Channel
Days per week watch TV: all 7 days
Past week: Watched broadcast or cable TV (live or DVR)
Past 3 months: celebrated my birthday (if applicable)
Commute to work/school: My own vehicle, Uber/Lyft
Coffee maker: Espresso machine
Job role: HR
First president of the United States: George Washington
Brands open to purchasing: Reebok, Tommy Hilfiger, Calvin Klein, Vineyard Vines, Levi's, Puma
Categories purchased past 12 months: Men's bags/accessories, Women's handbags, Men's dress shoes, Women's dress shoes, Men's apparel, Women's apparel, Beauty, Women's jewelry
Coffee/juice restaurants every 3 months: Starbucks, Dunkin Donuts
Back pain treatment past 6 months: A prescription topical pain reliever (cream, gel, spray, patch)
Household products owned: Washing Machine, Tablet/iPad, Blu-ray player, Refrigerator, Outdoor Barbecue Grill, Digital Camera, Riding Lawn Mower
Blood glucose 40 mg/dl → would most likely: Exercise
Caregiver contact with: Diabetes
Grocery stores monthly: Walmart, Target
Stores shop regularly: Walmart, Target
Ticket websites: Go Tickets, Tickets Now
Child's school type: Public school
Buy medication at pharmacy: Once a week, 4 times monthly
Planning to move next 12 months: No
COVID employment impact: No, my employment has not been affected
Health insurance type: Long Term Care; Employer-sponsored through my private company
Outdoor grills owned: Electric tabletop, Grill center, Built-in grill; paid 500-699
Video streaming services: Apple TV+, Amazon Prime Video, DirecTV Now, Netflix, YouTube Premium, HBO Max, Disney+, discovery+, ESPN+
Electronics owned: Flat screen/LCD TV, Blu-ray/DVD player, Portable game console, Digital SLR Camera, Desktop, Laptop, Cable/Satellite TV, Home Network/Wireless Internet, Tablet (iPad)
Gaming streaming subscriptions: Twitch TV
Opened new checking/savings account past year: Yes
Music types: Pop, Rock, Rock 'n' roll
Magazines read in print: Entertainment Weekly, ESPN The Magazine, Men's Health, Us Weekly
Magazines subscribed: Entertainment Weekly, Health, Us Weekly, Star, Travel + Leisure
Mortgage obtained: More than 2 years ago
Apply for new credit card next 6 months: Yes I might
Devices used with internet: Desktop PC, Regular laptop, Smartphone, Smart TV, Tablet
Primary auto/car/home insurance: State Farm
Saving for college: Yes, for my kids (general savings account)
Financial advice sources: Independent financial advisor/planner, Online investment forums, Subscription to professional research service
Company type worked for: services
Interest in Stocks/Bonds/Mutual Funds: Very Interested; own stocks: Yes
Role within HR: Employer-Employee relations
Internet connection at home: Cable, Wireless
Gambling: Car Race Betting (and others)
Sleep disorder diagnosis: None of the above
Cell phone: Yes, a smartphone with internet and apps
Annual household income before tax: 130,000-150,000
Mobile carrier: T-Mobile (5+ years); receive discounts directly from provider; no work/AAA discount
Coffee maker brand: Starbucks Verismo
Primary credit card issuer: Mastercard; BankAmericard (Bank of America); no annual fee; owned 6 years
Health apps/devices past 12 months: Fitness trackers, Fitness apps, Smartwatch with fitness function, Connected devices (scales, blood pressure meter)
Music streaming: Apple Music, Spotify, Amazon Music
Investable assets: $249,000 - $499,999
Online retailers past 30 days: Amazon, eBay, Kohls, Target.com, Walmart.com
Hobbies/interests: Fishing, Playing music, Playing video/computer games, Technology/Computers, Travel, Watching sports on TV
Hearing aid: No
Insurance shopped past 12 months: Health insurance
Hours video games per week: 12-14 hours; play 7+ times per week
Main vehicle purchased: 2018; primary auto decision maker: Yes
Pets present: Dog, Cat, Bird
Quit smoking methods tried: Nicotine lozenge, Nicotine gum
Radio hours per week: 5 hours or less
Mobile plan type: Prepaid (Individual)
Household decisions responsible for: Internet, Banking, Finance, Mortgage, Automobile
Illnesses/conditions: Anxiety, Back Pain, Depression, Diabetes
Own a motorcycle: Yes (Harley-Davidson Fat Boy, 2022, bought new 2023)
Healthcare past 3 months: Video/phone/text with a doctor other than primary care
Cancer type: I don't have cancer
Rent/download movies: 4-5 times per month
Jeans bought past 6 months: American Eagle, Banana Republic, Lee, Levi's, Old Navy
Do you smoke? Yes; 7-10 cigarettes per day
Activities: Swimming, Fishing, Badminton
Grocery delivery services past 6 months: Yes, regularly (Instacart/Shipt, 2+ times per month)
People in household: 4
Health insurance: Employer-Sponsored through my private company
Services used monthly: Lyft, Uber
Accommodation last 12 months: 4 star, 5 star
Diabetes type: Type 1
Registered to vote: Yes
Neurological/dermatology conditions: None of the above
Sports participate: Swimming, Badminton
Play games with others online: Yes
Primary TV provider: DIRECTV
Wine frequency: A few times per week
Car brand owned/leased: BMW
Heart attack date: N/A
Exercise hours per week: 6 to 8 hours
Online gaming: Yes
Social media platforms: Facebook, Twitter, LinkedIn, Instagram, YouTube, WhatsApp, TikTok, Snapchat
IT roles: IT Services Sourcing Manager
Snacks purchased/consumed: OREO Cookies, Hershey's Chocolate, Ben & Jerry's Ice Cream
Household purchases: candy/chocolate, carbonated beverages, cookies, ice cream, shampoo, soup
Alcoholic beverages: Beer, Champagne, Wine, Vodka
Beverages consumed: Coffee, Tea, Regular soda, Diet soda, Energy drinks, Sports Drink, Bottled water, Juice, Domestic/Imported beer, Red/White/Rosé wine, Champagne, Vodka
Shop online frequency: 12-15 times a month
Devices to play games: Console (offline), Laptop (offline), Cellphone/Smartphone/Handheld
Vehicle type: Luxury/Prestige (BMW/Mercedes)
CBD/Marijuana products: I use these products (for medicine/healing)
Hours of TV per week: 6 to 10 hours
System to buy next 12 months: Nintendo Switch, PlayStation 5
Access social media: Several times a day
Smartphone owned: iPhone 15
Vehicle bought new or used: New
Household illnesses: Anxiety, Back pain, Depression, Diabetes
Hepatitis type: none of the above
Early adopter of new technology: Yes
Video/computer games played: First Person Shooter/Action (Call of Duty), Sports (FIFA), RPG (Final Fantasy), Racing (Need for Speed)
Work in healthcare industry: No
Fast food per week: Four to six times
Lending products past 24 months: Automobile Loan, Credit Card
Banks with relationship: Bank of America, U.S. Bank, Wells Fargo
Glasses or contacts: Glasses
Work in education industry: No
Video games purchased per month: 2-3 games
International airlines flown: Emirates, Japan Airlines, Lufthansa, Mexicana
Domestic airlines flown: American Airlines, JetBlue, United Airlines, US Airways
Next car purchase: One to two years from now
Mobile phone type: Smart Phone
Cigarettes per day: 7-10
Vehicle year: 2017
Watch game streams (Twitch/YouTube): Yes, typically live streams
Cannabis/marijuana usage: For medicine/healing purposes
DVDs/Blu-rays purchased monthly: 4 to 6
Travel by plane purpose: Both leisure and business (Domestic Business 9, Domestic Personal 2, International Business 2, International Personal 1)
Job-related activities past year: Looked for a job, Used online social network to advance career
Drive a car regularly: Yes, I own a car/cars
Home mortgage provider: Bank of America
Alcoholic drinks per week: 1 to 3
Language at home: English all the time
Born in the United States: Yes
Movie theater genres: Action, Animated, Comedy, Documentary, Drama, Horror
Fast casual restaurants every 3-6 months: Boston Market, Friendly's, Habit Burger, Panda Express
Fast food restaurants visited: Burger King, Captain D's, Dunkin Donuts, KFC, McDonald's, Panda Express, Pizza Hut, Domino's, Popeyes, Subway, Starbucks, Taco Bell, Taco Time
Motor boat usage: Do not own but considering buying in next two years
Boat in: Saltwater
Countries traveled last 12 months: Central America, South America (Brazil), Japan, Middle East, Singapore
Publications read: Morning newspaper, Arts & crafts, Entertainment & gossip, Fashion/Style/Beauty, Travel magazines
Free video sites/apps: YouTube, YouTube Kids
TV channel apps: Cartoon Network App, Disney Now, HBO, Nick Jr. App
Use a smartphone: Business & Personal
Hours video games per week: More than 10 hours
Diabetes/thyroid/obesity: Type 1 diabetes
Spend on video games monthly: 400-600$
Religious/religion: very; Spiritual: very; Preference: Christian/Protestant
"""
