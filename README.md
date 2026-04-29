# FinTracker

The FinTracker is a web-based personal financial management application that enables users to upload bank statements for automated transaction extractions, categorize spending automatically using AI, track expenses and incomes, set monthly budgets, and generate analytical financial reports. The system aims to provide simplicity, accurate tracking, and automated insights for individuals seeking to improve their financial habits.

## Key Features & Impacts
* **Automated Data Ingestion & Categorization:** Eliminates manual data entry via a specialized Data Pipeline that processes PDF/CSV bank statements using computer vision (YOLOv8-Nano) and OCR (AWS Textract) to automatically extract and classify transactions.
* **ACID-Compliant Ledger:** Provides a highly reliable core financial engine built with Java Spring Boot and jOOQ, ensuring accurate tracking with strict tenant isolation and referential integrity.
* **Real-Time Financial Dashboard:** Calculates "Safe to Spend" metrics, tracks upcoming bills, and monitors time-series budgets dynamically, powered by instantaneous WebSocket push notifications and optimized OLAP analytics.
* **Intelligent Insights & Security:** Leverages AWS Bedrock for advanced spending anomaly detection while securing user authentication through AWS Cognito, ensuring total data privacy.

## Architecture
FinTracker is designed as a distributed, event-driven microservices architecture built on AWS. 

* **User Profile Service (Python/Serverless):** Manages user identity, static savings goals, and WebSocket connections utilizing a single-table design in DynamoDB.
* **Data Pipeline Service (Python/Step Functions):** An asynchronous ingestion engine that orchestrates document validation, OCR text extraction, and NLP merchant categorization.
* **Ledger Service (Java/Spring Boot):** The synchronous, ACID-compliant System of Record for all transactional data, enforcing rigorous Row-Level Security (RLS) patterns in PostgreSQL.
* **Analytics Service (Python/FastAPI):** Executes heavy OLAP aggregations and LLM-driven insights against a dedicated Postgres Read Replica to protect transactional performance.

## Tech Stack
* **Frontend:** Angular, TypeScript, Tailwind CSS
* **Backend:** Python (FastAPI) / Java (Spring Boot), PostgreSQL, DynamoDB
* **Cloud:** AWS (Lambda, S3, RDS, Bedrock, API Gateway, Step Functions, EventBridge, Cognito, Textract)
* **DevOps:** GitHub Actions, Docker, AWS CDK, Maven, Poetry

## Cloud & Security Best Practices
* **Multi-Tenant Data Isolation:** API Gateway validates JWTs and injects an `X-Internal-User-Id` header. The backend intercepts this and unconditionally applies it to all SQL queries, preventing cross-tenant data leaks.
* **Event-Driven Decoupling:** Heavy operations (like processing 50-page PDFs or cascading account deletions) are pushed to background queues (EventBridge/Step Functions) to protect synchronous REST API SLAs.
* **Infrastructure as Code (IaC):** The entire application environment, from API Gateways to DynamoDB tables, is provisioned predictably using AWS CDK.
* **Least Privilege:** AWS IAM execution roles are strictly scoped at the microservice level to access only required S3 buckets or database records.

## Quick Start
<details>
<summary>Click to expand setup instructions</summary>

### Prerequisites
* Java 21+ & Maven 3.9+
* Python 3.12+ & Poetry
* Node.js & Angular CLI
* Docker & Docker Compose
* AWS CLI configured with local developer credentials

### Installation
1.  **Clone the repository:**
    ```bash
    git clone https://github.com/vanKvo/fintracker.git
    cd fintracker
    ```
2.  **Launch Local Infrastructure:**
    Start the core PostgreSQL databases and local mocks via Docker Compose from the root directory.
    ```bash
    docker-compose up -d
    ```
3.  **Run Microservices:**
    Navigate into each `/services` folder to install dependencies and run the individual backend servers (e.g., `mvn spring-boot:run` for Ledger, `poetry run uvicorn` for Analytics).
4.  **Launch Frontend:**
    Navigate to the UI portal, install packages, and start the Angular server.
    ```bash
    cd fintracker-ui
    npm install
    ng serve
    ```
5.  **Access:**
    The application will be available at `http://localhost:4200`.

### Demo Data Management
To ensure a consistent demonstration experience, the database can be initialized with professional seed data. If the data is modified during a demo and needs to be reset:

1. **Stop the containers and remove the data volume:**
   ```bash
   docker-compose down -v
   ```
2. **Restart the stack:**
   ```bash
   docker-compose up -d
   ```
This will trigger the initialization scripts to recreate the database schemas and re-insert the original test data.

</details>
