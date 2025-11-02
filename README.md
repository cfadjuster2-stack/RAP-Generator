# RAP Estimate Generator - PDF Parser Microservice

Python-based microservice for parsing Xactimate estimate PDFs and extracting structured data for NFIP RAP compliance.

## Setup Instructions

### 1. Prerequisites
- Python 3.9 or higher
- pip (Python package manager)

### 2. Installation

```bash
# Create project directory
mkdir RAP-generator
cd RAP-generator

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

Create a `.env` file in the root directory:

```bash
cp .env.example .env
```

Edit `.env` with your settings:
- Set `OPENAI_API_KEY` if using AI-powered parsing fallback
- Adjust `ALLOWED_ORIGINS` for CORS (your WordPress site URL)
- Set `PORT` if you need a different port than 5001

### 4. Running Locally

```bash
cd api
python app.py
```

The service will start on `http://localhost:5001`

### 5. Testing

Place your test Xactimate PDFs in `tests/sample_pdfs/`

Test the API with curl:

```bash
curl -X POST http://localhost:5001/api/parse-estimate \
  -F "file=@tests/sample_pdfs/your-estimate.pdf"
```

Or use Postman/Insomnia to send POST requests with file uploads.

## API Endpoints

### `GET /health`
Health check endpoint

**Response:**
```json
{
  "status": "healthy",
  "service": "RAP Estimate Parser",
  "version": "1.0.0"
}
```

### `POST /api/parse-estimate`
Parse Xactimate estimate PDF

**Request:**
- Method: POST
- Content-Type: multipart/form-data
- Body: 
  - `file`: PDF file (required)
  - `options`: JSON object with parsing options (optional)

**Response:**
```json
{
  "success": true,
  "header": {
    "insured_name": "JOHN DOE",
    "property_address": "123 Main St, City, ST 12345",
    "claim_number": "123456",
    "policy_number": "POL-123456",
    "date_of_loss": "10/15/2024",
    "deductible": 1250.00
  },
  "line_items": [
    {
      "line_number": 1,
      "room": "KITCHEN",
      "description": "Remove base cabinets",
      "quantity": 16.0,
      "unit": "LF",
      "unit_price": 15.00,
      "tax": 0.00,
      "o_and_p": 0.00,
      "rcv": 240.00,
      "depreciation": 0.00,
      "acv": 240.00,
      "category": "CABINETRY"
    }
  ],
  "categories": [
    {
      "name": "CABINETRY",
      "rcv": 28000.00,
      "depreciation": 2100.00,
      "acv": 25900.00
    }
  ],
  "totals": {
    "rcv": 112000.00,
    "depreciation": 8400.00,
    "acv": 103600.00,
    "deductible": 1250.00,
    "net_claim": 102350.00
  }
}
```

## Project Structure

```
RAP-generator/
├── api/
│   ├── app.py                      # Main Flask application
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── xactimate_parser.py    # Core PDF parser
│   │   └── pdf_processor.py       # Additional processing utilities
│   ├── requirements.txt
│   └── .env
├── tests/
│   └── sample_pdfs/               # Your test PDFs
└── README.md
```

## Development Roadmap

- [x] Phase 1: PDF Parser Microservice
  - [x] Flask API setup
  - [x] PyMuPDF parser
  - [x] pdfplumber fallback
  - [x] Header extraction
  - [x] Line item extraction
  - [x] Category extraction
- [ ] Phase 2: Enhanced Parsing
  - [ ] Table extraction improvement
  - [ ] OCR for scanned PDFs
  - [ ] OpenAI intelligent parsing
- [ ] Phase 3: WordPress Integration
- [ ] Phase 4: Cost Distribution Engine
- [ ] Phase 5: PDF Generation

## Next Steps

1. **Test with your 3 PDFs**: Place them in `tests/sample_pdfs/` and test the parser
2. **Review extraction accuracy**: Check if all data is being captured correctly
3. **Iterate on parsing logic**: We'll refine based on your actual PDF formats
4. **Deploy to Railway**: Once working locally, deploy for production use

## Support

Contact: Christopher (FloodAI Team)