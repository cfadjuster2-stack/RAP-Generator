"""
RAP Estimate Generator - Flask API
Main application file for PDF parsing microservice
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import os
import logging
from werkzeug.utils import secure_filename
import traceback

from parsers.xactimate_parser import XactimateParser

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# CORS configuration
allowed_origins = os.getenv('ALLOWED_ORIGINS', '*').split(',')
CORS(app, origins=allowed_origins)

# File upload configuration
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_FILE_SIZE_MB', 50)) * 1024 * 1024
UPLOAD_FOLDER = 'temp_uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Allowed file extensions
ALLOWED_EXTENSIONS = set(os.getenv('ALLOWED_EXTENSIONS', 'pdf').split(','))


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'RAP Estimate Parser',
        'version': '1.0.0'
    }), 200


@app.route('/api/parse-estimate', methods=['POST'])
def parse_estimate():
    """
    Parse Xactimate estimate PDF and extract structured data
    
    Expected form data:
    - file: PDF file
    - options: JSON object with parsing options (optional)
    """
    try:
        # Check if file is present
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Only PDF files allowed'}), 400
        
        # Save file temporarily
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        logger.info(f"Processing PDF: {filename}")
        
        # Parse options from request
        options = {}
        if 'options' in request.form:
            import json
            options = json.loads(request.form['options'])
        
        # Initialize parser and process PDF
        parser = XactimateParser()
        result = parser.parse_pdf(filepath, options)
        
        # Clean up temporary file
        os.remove(filepath)
        
        if result.get('success'):
            logger.info(f"Successfully parsed {filename}")
            return jsonify(result), 200
        else:
            logger.error(f"Failed to parse {filename}: {result.get('error')}")
            return jsonify(result), 422
            
    except Exception as e:
        logger.error(f"Error processing PDF: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Clean up file if it exists
        if 'filepath' in locals() and os.path.exists(filepath):
            os.remove(filepath)
        
        return jsonify({
            'success': False,
            'error': 'Internal server error processing PDF',
            'details': str(e)
        }), 500


@app.route('/api/validate-estimate', methods=['POST'])
def validate_estimate():
    """
    Validate parsed estimate data against NFIP RAP rules
    
    Expected JSON body:
    - estimate_data: Parsed estimate object
    """
    try:
        data = request.get_json()
        
        if not data or 'estimate_data' not in data:
            return jsonify({'error': 'No estimate data provided'}), 400
        
        # TODO: Implement NFIP validation rules
        # For now, return placeholder
        
        return jsonify({
            'success': True,
            'valid': True,
            'warnings': [],
            'errors': []
        }), 200
        
    except Exception as e:
        logger.error(f"Error validating estimate: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file too large error"""
    max_size = app.config['MAX_CONTENT_LENGTH'] / (1024 * 1024)
    return jsonify({
        'error': f'File too large. Maximum size is {max_size}MB'
    }), 413


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5001))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    logger.info(f"Starting RAP Estimate Parser API on port {port}")
    logger.info(f"Debug mode: {debug}")
    
    app.run(host='0.0.0.0', port=port, debug=debug)