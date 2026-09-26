web: uvicorn api.app:app --host 0.0.0.0 --port $PORT
worker: python -m worker.worker
streamlit: streamlit run streamlit_app.py --server.port $PORT --server.address 0.0.0.0
