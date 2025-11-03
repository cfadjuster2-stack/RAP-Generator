# PDF Export Fix - Line Item Distribution

## Issue
The PDF export was:
1. Not working (bug with `exportSummary` variable)
2. Only showing category summaries instead of all line items
3. Not distributing contractor pricing across individual line items

## Solution
Updated `src/components/ContractorDetails.jsx` to:

1. **Fix the export bug** - corrected variable references
2. **Distribute contractor pricing** - proportionally across all line items in each category
3. **Generate estimate-style PDF** - showing all line items with revised pricing in a format similar to the original IA estimate

## Key Changes

### 1. Added Pricing Distribution Function

```javascript
const distributeContractorPricing = () => {
  const grouped = groupByCategory(lineItems);
  const distributedItems = [];

  Object.entries(grouped).forEach(([category, items]) => {
    const contractorPrice = parseFloat(pricing[category]?.contractorPrice);

    if (contractorPrice > 0) {
      // Calculate original category total
      const categoryTotal = items.reduce((sum, item) => sum + (item.rcv || 0), 0);

      if (categoryTotal > 0) {
        // Distribute proportionally
        items.forEach(item => {
          const proportion = (item.rcv || 0) / categoryTotal;
          const newRCV = contractorPrice * proportion;
          const newUnitPrice = item.quantity > 0 ? newRCV / item.quantity : 0;

          distributedItems.push({
            ...item,
            original_rcv: item.rcv,
            original_unit_price: item.unit_price,
            rcv: newRCV,
            unit_price: newUnitPrice,
            adjustment: newRCV - (item.rcv || 0)
          });
        });
      }
    } else {
      // No contractor price - keep original
      distributedItems.push(...items.map(item => ({ ...item, adjustment: 0 })));
    }
  });

  return distributedItems;
};
```

### 2. Updated PDF Generation

The PDF now shows:
- **Header** with claim info and contractor details
- **All line items** grouped by category
- **Each line** shows: Description, Qty/Unit, Original Unit Price, New Unit Price, Original RCV, Revised RCV
- **Category subtotals** with adjustments
- **Grand totals** showing overall adjustment

### 3. PDF Format

The exported PDF looks like an estimate with columns:
```
#  | Description | Qty/Unit | Orig Unit $ | New Unit $ | Original RCV | Revised RCV
```

## How It Works

**Example:**

If CLEANING category has:
- Line 1: "Clean walls" - $500 RCV (50% of category)
- Line 2: "Muck out" - $500 RCV (50% of category)
- **Category Total:** $1,000

Contractor enters: $1,200 for CLEANING

**Distribution:**
- Line 1: $1,200 × 50% = $600 (was $500, +$100)
- Line 2: $1,200 × 50% = $600 (was $500, +$100)

The PDF shows both original and revised pricing for each line.

## Manual Update Steps

Since the automated update had issues, here's how to manually apply the fix:

1. **Open:** `C:\Users\cfadj\rap-frontend\src\components\ContractorDetails.jsx`

2. **Find the `handleExportPDF` function** (around line 34)

3. **Replace the entire function** with the updated version (see attached file: `ContractorDetails_FIXED.jsx`)

Key sections to update:
- Add the `distributeContractorPricing()` function before `handleExportPDF`
- Update the PDF generation code inside `handleExportPDF` to use line items
- Change the PDF table to show all line items with columns for original vs revised pricing

## Testing

After applying the fix:

1. Upload an estimate
2. Review categories
3. Enter contractor pricing (e.g., CLEANING: $6,000)
4. Enter contractor details
5. Click "Export RAP Estimate PDF"
6. Check the downloaded PDF:
   - Should show all line items
   - Should show original vs revised pricing
   - Should calculate adjustments per line

## Full Updated Code

The complete updated `ContractorDetails.jsx` file is available at:
`C:\Users\cfadj\rap-generator\ContractorDetails_FIXED.jsx`

Copy this file to:
`C:\Users\cfadj\rap-frontend\src\components\ContractorDetails.jsx`

Then restart your dev server and test the export!

## Alternative: Quick Fix for Testing

If you want to test immediately, you can make just the critical fix:

In `handleExportPDF`, find this line around line 50:
```javascript
const exportSummary = cats.map(category => {
```

And ensure the variable `exportSummary` is actually used, not `summary` (or rename it to `summary` throughout).

This will at least make the export work, even if it's not showing line items yet.
