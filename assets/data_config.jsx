// ============================================
// DATA CONFIGURATION
// ============================================

const MINERALS = [
    'Tritanium', 'Pyerite', 'Isogen', 'Mexallon',
    'Nocxium', 'Zydrine', 'Megacyte', 'Morphite'
];

const ICE_PRODUCTS = [
    'Heavy Water', 'Liquid Ozone', 'Strontium Clathrates',
    'Oxygen Isotopes', 'Hydrogen Isotopes', 'Helium Isotopes', 'Nitrogen Isotopes'
];

const MOON_MATERIALS = {
    'R4 - Ubiquitous': ['Atmospheric Gases', 'Evaporite Deposits', 'Hydrocarbons', 'Silicates'],
    'R8 - Common': ['Cobalt', 'Scandium', 'Tungsten', 'Titanium'],
    'R16 - Uncommon': ['Chromium', 'Cadmium', 'Platinum', 'Vanadium'],
    'R32 - Rare': ['Technetium', 'Mercury', 'Caesium', 'Hafnium'],
    'R64 - Exceptional': ['Promethium', 'Neodymium', 'Dysprosium', 'Thulium']
};

const SALVAGE_MATERIALS = {
    'Common': [
        'Scorched Telemetry Processor', 'Malfunctioning Shield Emitter',
        'Smashed Trigger Unit', 'Alloyed Tritanium Bar',
        'Broken Drone Transceiver', 'Damaged Artificial Neural Network',
        'Tripped Power Circuit', 'Charred Micro Circuit'
    ],
    'Uncommon': [
        'Contaminated Nanite Compound', 'Contaminated Lorentz Fluid',
        'Defective Current Pump', 'Tangled Power Conduit',
        'Burned Logic Circuit', 'Fried Interface Circuit',
        'Thruster Console', 'Melted Capacitor Console',
        'Conductive Polymer', 'Armor Plates', 'Ward Console'
    ],
    'Rare': [
        'Telemetry Processor', 'Current Pump', 'Power Conduit',
        'Single-crystal Superalloy I-beam', 'Drone Transceiver',
        'Artificial Neural Network', 'Micro Circuit',
        'Interface Circuit', 'Impetus Console', 'Conductive Thermoplastic'
    ],
    'Very Rare': [
        'Intact Shield Emitter', 'Nanite Compound', 'Lorentz Fluid',
        'Trigger Unit', 'Power Circuit', 'Logic Circuit',
        'Capacitor Console', 'Intact Armor Plates', 'Enhanced Ward Console'
    ],
    'Rogue Drone': [
        'Drone Synaptic Relay Wiring', 'Drone Capillary Fluid',
        'Drone Cerebral Fragment', 'Drone Tactical Limb',
        'Drone Epidermal Shielding Chunk', 'Drone Coronary Unit',
        'Elite Drone AI', 'Drone Graviton Emitter'
    ]
};

let allBlueprints = [];
let filteredBlueprints = [];

// ============================================
// EMBEDDED DATA
// ============================================
const EMBEDDED_DATA = {
    "inventory": {
                "Alloyed Tritanium Bar": 21,
                "Armor Plates": 3,
                "Artificial Neural Network": 1,
                "Atmospheric Gases": 106529,
                "Broken Drone Transceiver": 62,
                "Burned Logic Circuit": 107,
                "Cadmium": 2419,
                "Caesium": 0,
                "Capacitor Console": 0,
                "Charred Micro Circuit": 52,
                "Chromium": 7330,
                "Cobalt": 5519,
                "Conductive Polymer": 6,
                "Conductive Thermoplastic": 0,
                "Contaminated Lorentz Fluid": 4,
                "Contaminated Nanite Compound": 6,
                "Current Pump": 0,
                "Damaged Artificial Neural Network": 34,
                "Defective Current Pump": 9,
                "Drone Capillary Fluid": 0,
                "Drone Cerebral Fragment": 8,
                "Drone Coronary Unit": 0,
                "Drone Epidermal Shielding Chunk": 0,
                "Drone Graviton Emitter": 0,
                "Drone Synaptic Relay Wiring": 59,
                "Drone Tactical Limb": 70,
                "Drone Transceiver": 0,
                "Dysprosium": 0,
                "Elite Drone AI": 1,
                "Enhanced Ward Console": 0,
                "Evaporite Deposits": 130044,
                "Fried Interface Circuit": 156,
                "Hafnium": 0,
                "Heavy Water": 871412,
                "Helium Isotopes": 295200,
                "Hydrocarbons": 0,
                "Hydrogen Isotopes": 295200,
                "Impetus Console": 0,
                "Intact Armor Plates": 0,
                "Intact Shield Emitter": 7,
                "Interface Circuit": 1,
                "Isogen": 1991019,
                "Liquid Ozone": 315044,
                "Logic Circuit": 6,
                "Lorentz Fluid": 0,
                "Malfunctioning Shield Emitter": 11,
                "Megacyte": 124006,
                "Melted Capacitor Console": 5,
                "Mercury": 0,
                "Mexallon": 11175954,
                "Micro Circuit": 0,
                "Morphite": 133,
                "Nanite Compound": 0,
                "Neodymium": 10909,
                "Nitrogen Isotopes": 771973,
                "Nocxium": 635557,
                "Oxygen Isotopes": 295200,
                "Platinum": 0,
                "Power Circuit": 0,
                "Power Conduit": 0,
                "Promethium": 7314,
                "Pyerite": 77517315,
                "Scandium": 6690,
                "Scorched Telemetry Processor": 83,
                "Silicates": 103615,
                "Single-crystal Superalloy I-beam": 0,
                "Smashed Trigger Unit": 4,
                "Strontium Clathrates": 18023,
                "Tangled Power Conduit": 8,
                "Technetium": 27585,
                "Telemetry Processor": 0,
                "Thruster Console": 1,
                "Thulium": 0,
                "Titanium": 6050,
                "Trigger Unit": 0,
                "Tripped Power Circuit": 110,
                "Tritanium": 136517157,
                "Tungsten": 14464,
                "Vanadium": 0,
                "Ward Console": 36,
                "Zydrine": 621668
    },
    "blueprintsLastUpdated": "Feb 21, 2026 08:00 EVE",
    "inventoryLastUpdated": "Feb 21, 2026 20:08 EVE"
};