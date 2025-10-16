import os
import sys
import json
import re
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
from sqlalchemy import create_engine
import pymssql
from langchain_community.utilities import SQLDatabase
from langchain_openai import AzureChatOpenAI
from langchain_community.agent_toolkits import create_sql_agent

# --- INITIALIZATION ---
load_dotenv("/etc/secrets/.env")  # Load secrets from Render's secure Secret File
app = Flask(__name__)
CORS(app)
api_details_cache = {}

# --- DATABASE AND AI SETUP ---
MODULE_TO_TABLE_MAP = {
    "Master DB": ["Trials", "Drug", "Company"],
    "Drugs DB": ["Drug"], "Companies DB": ["Company"], "Clinical Trials DB": ["Trials"],
    "Sales Forecast DB": [], "Patents DB": [], "Drug Pricing DB": [], "Market Access": [],
    "Deals DB": [], "Epidemiology DB": [], "Manufacturing DB": [], "Exim DB": []
}
TABLE_TO_MODULE_MAP = {
    "Trials": "Clinical Trials DB", "Drug": "Drugs DB", "Company": "Companies DB",
}

# --- SQL Server Connection via pymssql.connect ---
SERVER = os.getenv("DB_SERVER")
PORT = os.getenv("DB_PORT", "1433")
DATABASE = os.getenv("DB_DATABASE")
USERNAME = os.getenv("DB_USERNAME")
PASSWORD = os.getenv("DB_PASSWORD")

def db_connector():
    return pymssql.connect(
        server=SERVER,
        port=int(PORT),
        user=USERNAME,
        password=PASSWORD,
        database=DATABASE,
        timeout=10
    )

try:
    print("Initializing database engine...")
    engine = create_engine("mssql+pymssql://", creator=db_connector, echo=True)
    with engine.connect() as connection:
        print("✅ Database connection successful!")
except Exception as e:
    print(f"❌ FAILED TO CONNECT TO DATABASE. Error: {e}")
    sys.exit(1)

# --- Azure OpenAI Setup ---
llm = AzureChatOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    openai_api_version=os.getenv("AZURE_API_VERSION"),
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
    temperature=0,
)

# --- API ENDPOINT 1: Proactive Counts AND Data Fetching/Caching ---
@app.route("/api/query", methods=["POST"])
def handle_query():
    try:
        data = request.get_json()
        user_query = data.get("query")
        selected_dbs = data.get("selected_dbs", [])
        print(f"--- Received query: '{user_query}' for DBs: {selected_dbs} ---")

        if not selected_dbs:
            return jsonify({"error": "No databases were selected."}), 400

        allowed_tables = set()
        for db_name in selected_dbs:
            tables = MODULE_TO_TABLE_MAP.get(db_name, [])
            allowed_tables.update(tables)
        allowed_tables = list(allowed_tables)
        print(f"Scope of search limited to tables: {allowed_tables}")

        if not allowed_tables:
            return jsonify({
                "summary": "The selected modules have no associated data tables.",
                "module_counts": {}
            })

        module_counts = {}
        for table_name in allowed_tables:
            module_name = TABLE_TO_MODULE_MAP.get(table_name)
            if not module_name:
                continue

            print(f"--- Processing module: {module_name} for table: {table_name} ---")
            db = SQLDatabase(engine, include_tables=[table_name])
            agent_executor = create_sql_agent(llm, db=db, agent_type="openai-tools", verbose=True)

            count_query = f"How many records in the {table_name} table are related to '{user_query}'?"
            count_result = agent_executor.invoke(count_query)
            count_str = ''.join(filter(str.isdigit, count_result.get("output", "0")))
            count = int(count_str) if count_str else 0

            if count > 0:
                module_counts[module_name] = count
                cache_key = (user_query, module_name)
                print(f"Proactively fetching and caching details for {cache_key}...")

                detailed_prompt = (
                    f"A user is asking about '{user_query}'. Focus on the '{module_name}'. "
                    f"1. Decide the most relevant columns in the {table_name} table. "
                    f"2. Write and execute a SQL query for those columns for all matching records. "
                    f"3. Analyze the data and write a brief explanation. "
                    f"4. Return a JSON object with 'summary' and 'data' keys."
                )
                details_result = agent_executor.invoke(detailed_prompt)
                json_string = details_result['output'][details_result['output'].find('{'):details_result['output'].rfind('}')+1]
                ai_data = json.loads(json_string)

                final_details_response = {
                    "aiSummary": ai_data.get("summary"),
                    "tables": [{
                        "title": f"Data for {module_name}",
                        "data": ai_data.get("data")
                    }]
                }
                api_details_cache[cache_key] = final_details_response
                print(f"✅ Cached details for {cache_key}")

        summary_prompt = (
            f"A user searched for '{user_query}'. We found these results: {module_counts}. "
            f"Write a brief, one-sentence summary of the findings."
        )
        summary_response = llm.invoke(summary_prompt)
        ai_summary = summary_response.content

        return jsonify({
            "summary": ai_summary,
            "module_counts": module_counts
        })
    except Exception as e:
        print(f"An error occurred in /api/query: {e}")
        return jsonify({"error": str(e)}), 500

# --- API ENDPOINT 2: Fast Cache Lookup ---
@app.route("/api/details", methods=["POST"])
def handle_details():
    data = request.get_json()
    user_query = data.get("query")
    module = data.get("module")
    cache_key = (user_query, module)

    if cache_key in api_details_cache:
        print(f"✅ Returning CACHED result for: {cache_key}")
        return jsonify(api_details_cache[cache_key])
    else:
        print(f"❌ CACHE MISS for {cache_key}.")
        return jsonify({
            "error": "Data not found in cache. This can happen if the initial search was too broad or failed for this module. Please start a new search."
        }), 404

if __name__ == "__main__":
    app.run(debug=True, port=5000, use_reloader=False)