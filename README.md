# SQS WeBuddhist Segment Mapping Uploader

A Python-based SQS consumer service that processes segment mapping jobs and uploads them to the WeBuddhist API.

## Features

- AWS SQS consumer for processing manifestation mapping requests
- PostgreSQL database integration for job tracking
- Automatic mapping upload to WeBuddhist API
- Comprehensive logging and error handling

## Prerequisites

- Python 3.12+
- PostgreSQL database
- AWS account with SQS access
- WeBuddhist API credentials

## Installation

1. Clone the repository:
```bash
git clone https://github.com/OpenPecha/sqs-webuddhist-segment-mapping-uploader.git
cd sqs-webuddhist-segment-mapping-uploader
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the project root with your configuration:
```env
# Database
POSTGRES_URL=postgresql://user:password@localhost:5432/dbname

# AWS SQS
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/account-id/queue-name

# WeBuddhist API
WEBUDDHIST_API_ENDPOINT=https://api.webuddhist.com
WEBUDDHIST_LOG_IN_EMAIL=your_email@example.com
WEBUDDHIST_LOG_IN_PASSWORD=your_password
```

## Usage

### Running the SQS Consumer

Start the consumer to listen for messages from the SQS queue:

```bash
python -m app.main
```

The consumer will:
1. Listen for messages containing `manifestation_id`
2. Fetch segment mappings from the PostgreSQL database
3. Format the payload for WeBuddhist API
4. Upload the mappings to WeBuddhist

### Manual Upload

You can also run the uploader manually for testing:

```bash
python -m app.uploader
```

Enter the manifestation ID when prompted.

## Project Structure

```
.
├── app/
│   ├── config.py           # Configuration management
│   ├── main.py             # SQS consumer entry point
│   ├── models.py           # Pydantic data models
│   ├── uploader.py         # Core upload logic
│   └── db/
│       ├── models.py       # SQLAlchemy database models
│       └── postgres.py     # Database connection setup
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (not in git)
├── .gitignore             # Git ignore rules
└── README.md              # This file
```

## Message Format

The SQS consumer expects messages in the following JSON format:

```json
{
  "manifestation_id": "your-manifestation-id-here"
}
```

## Database Schema

The application expects the following PostgreSQL tables:

- `RootJob`: Contains job information including `manifestation_id`, `job_id`, `total_segments`, and `completed_segments`
- `SegmentTask`: Contains individual segment tasks with `task_id`, `job_id`, `segment_id`, `status`, and `result_json`

## Development

### Testing SQS Connection

To verify your AWS SQS configuration:

```bash
python test_sqs.py
```

## Deployment

### Render

This application is designed to be deployed as a Background Worker on Render:

1. Push your code to GitHub
2. Create a new Background Worker on Render
3. Connect your GitHub repository
4. Set the start command: `python -m app.main`
5. Add all environment variables from your `.env` file
6. Create a PostgreSQL database on Render and update `POSTGRES_URL`

## License

MIT

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

