@echo off
cd /d "%~dp0"
python -m streamlit run app.py
pause
```

2. Place it in your `device_database` folder:
```
device_database/
├── app.py
├── requirements.txt
├── README.md
├── launch.bat
└── .streamlit/
    └── config.toml