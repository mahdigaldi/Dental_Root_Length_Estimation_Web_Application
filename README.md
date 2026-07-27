<img width="1122" height="1402" alt="image" src="https://github.com/user-attachments/assets/28549c77-0bb3-4649-99d9-6f100d4650e6" /><img width="1122" height="1402" alt="image" src="https://github.com/user-attachments/assets/15c091c8-3810-4536-b570-25312323113c" />




🦷 Dental Root Length Estimation Web Application

This project is a Flask-based web application for automatic dental radiograph analysis using Deep Learning. It detects primary molars (D/E teeth) from periapical X-ray images and estimates root length in millimeters through multiple prediction strategies.

The application integrates a YOLO-based object detector with machine learning regression models to provide accurate root length estimation. Users can upload a dental radiograph through a simple web interface and receive annotated images together with detailed prediction results.

✨ Features
Automatic detection of primary molars (D and E teeth)
Root length estimation in millimeters
Three prediction modes:
YOLO-based estimation
Alternative regression model
Ensemble prediction
Annotated output images
Interactive Flask web interface
REST API for integration with external applications
Configurable confidence thresholds and ensemble weights
Ready for deployment on Windows IIS, VPS, or cPanel hosting
⚙️ Technologies
Python
Flask
YOLO (Ultralytics)
OpenCV
PyTorch
Scikit-learn
Joblib
📌 Applications
Computer-Aided Dental Diagnosis (CAD)
Pediatric Dentistry
Dental Image Analysis
AI-assisted Root Length Measurement
Research and Clinical Decision Support
