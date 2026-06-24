"""Indian states/UTs and their popular travel destinations."""

STATES: dict = {
    "Andaman & Nicobar Islands": ["Port Blair", "Havelock Island", "Neil Island", "Baratang Island", "Ross Island"],
    "Andhra Pradesh": ["Visakhapatnam", "Tirupati", "Araku Valley", "Vijayawada", "Horsley Hills", "Lepakshi"],
    "Arunachal Pradesh": ["Tawang", "Ziro", "Namdapha", "Bomdila", "Mechuka", "Along"],
    "Assam": ["Kaziranga", "Guwahati", "Majuli", "Tezpur", "Manas", "Hajo"],
    "Bihar": ["Bodh Gaya", "Patna", "Nalanda", "Rajgir", "Vaishali", "Pawapuri"],
    "Chandigarh": ["Chandigarh"],
    "Chhattisgarh": ["Jagdalpur", "Raipur", "Chitrakote Falls", "Sirpur", "Barnawapara", "Achanakmar"],
    "Delhi": ["Delhi", "Old Delhi", "Qutub Minar area", "Lodhi Garden", "Hauz Khas"],
    "Goa": ["North Goa", "South Goa", "Panaji", "Calangute", "Anjuna", "Palolem", "Vagator", "Colva"],
    "Gujarat": ["Rann of Kutch", "Ahmedabad", "Somnath", "Dwarka", "Sasan Gir", "Vadodara", "Rajkot", "Saputara"],
    "Haryana": ["Kurukshetra", "Morni Hills", "Sultanpur Bird Sanctuary", "Faridabad"],
    "Himachal Pradesh": ["Shimla", "Manali", "Dharamsala & McLeod Ganj", "Spiti Valley", "Kullu", "Kasauli", "Dalhousie", "Chail", "Kaza"],
    "Jammu & Kashmir": ["Srinagar", "Gulmarg", "Pahalgam", "Sonamarg", "Vaishno Devi", "Patnitop", "Dal Lake"],
    "Jharkhand": ["Ranchi", "Jamshedpur", "Netarhat", "Deoghar", "Betla National Park"],
    "Karnataka": ["Coorg (Kodagu)", "Hampi", "Mysore", "Gokarna", "Chikmagalur", "Badami", "Bangalore", "Dandeli", "Udupi", "Sakleshpur"],
    "Kerala": ["Munnar", "Alleppey (Alappuzha)", "Kochi", "Thekkady", "Varkala", "Kovalam", "Wayanad", "Kumarakom", "Bekal"],
    "Ladakh": ["Leh", "Pangong Lake", "Nubra Valley", "Zanskar Valley", "Tso Moriri", "Khardung La"],
    "Lakshadweep": ["Agatti", "Bangaram", "Kavaratti", "Minicoy"],
    "Madhya Pradesh": ["Khajuraho", "Pachmarhi", "Orchha", "Kanha", "Bandhavgarh", "Jabalpur & Bhedaghat", "Bhopal", "Ujjain", "Pench"],
    "Maharashtra": ["Lonavala & Khandala", "Mahabaleshwar", "Nashik", "Aurangabad & Ajanta-Ellora", "Shirdi", "Mumbai", "Pune", "Alibaug", "Matheran", "Kolhapur"],
    "Manipur": ["Imphal", "Loktak Lake", "Ukhrul", "Moreh"],
    "Meghalaya": ["Shillong", "Cherrapunji (Sohra)", "Mawlynnong", "Dawki", "Nohkalikai Falls", "Mawsmai Cave"],
    "Mizoram": ["Aizawl", "Champhai", "Phawngpui Blue Mountain", "Reiek"],
    "Nagaland": ["Kohima", "Dimapur", "Hornbill Festival grounds", "Dzukou Valley"],
    "Odisha": ["Puri", "Bhubaneswar", "Konark", "Chilika Lake", "Simlipal", "Daringbadi"],
    "Puducherry": ["Puducherry (Pondicherry)", "Auroville", "Paradise Beach"],
    "Punjab": ["Amritsar", "Anandpur Sahib", "Chandigarh", "Pathankot", "Ludhiana"],
    "Rajasthan": ["Jaipur", "Jodhpur", "Udaipur", "Jaisalmer", "Pushkar", "Mount Abu", "Ranthambore", "Bikaner", "Chittorgarh", "Ajmer"],
    "Sikkim": ["Gangtok", "Pelling", "Lachung", "Yuksom", "Ravangla", "Zuluk"],
    "Tamil Nadu": ["Ooty (Udhagamandalam)", "Kodaikanal", "Madurai", "Mahabalipuram", "Kanyakumari", "Rameswaram", "Chennai", "Yelagiri", "Coimbatore", "Vellore"],
    "Telangana": ["Hyderabad", "Warangal", "Nagarjunasagar", "Medak", "Bhongir"],
    "Tripura": ["Agartala", "Neermahal", "Ujjayanta Palace", "Unakoti"],
    "Uttar Pradesh": ["Agra & Taj Mahal", "Varanasi", "Lucknow", "Ayodhya", "Mathura & Vrindavan", "Prayagraj", "Dudhwa"],
    "Uttarakhand": ["Rishikesh", "Haridwar", "Mussoorie", "Nainital", "Auli", "Jim Corbett", "Valley of Flowers", "Chopta", "Lansdowne", "Ranikhet"],
    "West Bengal": ["Darjeeling", "Kolkata", "Kalimpong", "Sundarbans", "Digha", "Shantiniketan", "Siliguri"],
}

# Sorted for the dropdown
STATE_NAMES = sorted(STATES.keys())

# Major Indian departure cities for the "Departing from" field
DEPARTURE_CITIES = sorted([
    "Ahmedabad", "Amritsar", "Aurangabad", "Bangalore", "Bhopal", "Bhubaneswar",
    "Chandigarh", "Chennai", "Coimbatore", "Delhi", "Goa", "Guwahati",
    "Hyderabad", "Indore", "Jaipur", "Kolkata", "Kochi", "Lucknow",
    "Mangalore", "Mumbai", "Nagpur", "Patna", "Pune", "Raipur",
    "Ranchi", "Srinagar", "Surat", "Thiruvananthapuram", "Vadodara",
    "Varanasi", "Visakhapatnam",
])
