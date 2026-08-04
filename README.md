# FinTracker

FinTracker is a privacy-first, web-based financial data platform that enables users to analyze and manage their finances by uploading bank statements instead of connecting bank accounts directly. The system transforms raw financial documents into structured, queryable data for spending analysis, budgeting, and financial reporting.

Unlike traditional personal finance applications that rely on direct bank integrations, FinTracker is designed around a document-based ingestion model. Users can upload bank statements (e.g., PDF, CSV, or images), which are processed through an automated pipeline to extract, normalize, and categorize transactions.

This approach allows users to maintain full control over their financial data while still benefiting from automated analysis, budgeting tools, and AI-driven insights.

The platform is designed to support individuals and households who prefer a privacy-preserving alternative to bank-connected financial apps.

## Key Features & Impacts
* **Statement-Based Data Ingestion:** Upload bank statements (PDF/CSV/image) for automated extraction of financial transactions.
* **Transaction Processing Pipeline:** Extract, normalize, and structure raw financial data into a unified schema for downstream analysis.
* **Spending Categorization:** Classify transactions into meaningful categories using rule-based logic and AI-assisted models.
* **Budget Tracking:** Define monthly budgets and track spending against categorized transaction data.
* **Financial Reporting:** Generate structured summaries of income, expenses, and spending trends.
* **AI-Powered Insights:** Generate natural-language explanations of spending patterns and budget variances using LLM-based services.

## Architecture
FinTracker is designed as a distributed, event-driven microservices architecture built on AWS. 

* **User Profile Service (Python/Serverless):** Manages user identity, static savings goals, and WebSocket connections utilizing a single-table design in DynamoDB.
* **Data Pipeline Service (Python/Step Functions):** An asynchronous ingestion engine that orchestrates document validation, OCR text extraction, and NLP merchant categorization.
* **Ledger Service (Java/Spring Boot):** The synchronous, ACID-compliant System of Record for all transactional data, enforcing rigorous Row-Level Security (RLS) patterns in PostgreSQL.
* **Analytics Service (Python/FastAPI):** Executes heavy OLAP aggregations and LLM-driven insights against a dedicated Postgres Read Replica to protect transactional performance.

## Tech Stack
* **Frontend:** Angular, TypeScript, Tailwind CSS
* **Backend:** Python (FastAPI) / Java (Spring Boot), PostgreSQL, DynamoDB
* **Cloud:** AWS (Lambda, S3, RDS, Comprehend, Bedrock, API Gateway, Step Functions, EventBridge, Cognito, Textract)
* **DevOps:** GitHub Actions, Docker, AWS (CDK, SAM), Maven, Poetry

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

## License 
MIT