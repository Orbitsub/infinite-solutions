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