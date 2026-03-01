// Auto-generated BPC pricing data
// Updated automatically - do not manually edit

// Pricing configuration
const BPC_PRICING_CONFIG = {
    formula: "per_run = Jita 7-day avg best sell × 1% × quality",
    priceSource: "7-day avg best sell from market snapshots",
    basePercentage: 0.01,  // 1% of Jita best sell at 100% quality
    qualityFormula: "0.25 + (ME/10 × 0.60) + (TE/20 × 0.15)"
};

// Blueprint pricing data
const BPC_PRICING_DATA = [];

// Helper function to calculate custom pricing
function calculateBPCPrice(blueprintTypeId, runs, copies) {
    const bp = BPC_PRICING_DATA.find(b => b.blueprintTypeId === blueprintTypeId);
    if (!bp) return null;

    // Price scales linearly with runs and copies
    const pricePerRun = bp.pricePerRun;
    const totalPrice = pricePerRun * runs * copies;

    return {
        blueprintName: bp.blueprintName,
        me: bp.me,
        te: bp.te,
        quality: bp.quality,
        qualityPercent: bp.qualityPercent,
        jitaSellPrice: bp.jitaSellPrice,
        runs: runs,
        copies: copies,
        totalRuns: runs * copies,
        pricePerRun: pricePerRun,
        totalPrice: totalPrice
    };
}
