# C4 Repository Analytics

A Streamlit application to track and analyze C4 diagram repositories for Sympla.

## Features

- Fetch C4 diagram data from GitLab repositories
- Map and display C4 elements (container, application, service, webapp, mobile, database, queue)
- Track repository documentation progress
- Import critical repositories from CSV
- Monitor documentation completeness with progress bars
- Configurable minimum documentation requirements

## Setup

1. Create a virtual environment:
   ```
   python3 -m venv venv
   ```

2. Activate the virtual environment:
   - On macOS/Linux:
     ```
     source venv/bin/activate
     ```
   - On Windows:
     ```
     venv\Scripts\activate
     ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Run the application:
   ```
   streamlit run app.py
   ```

## Usage

1. **Setup Area (Left Sidebar)**:
   - Enter your GitLab token (if needed for private repositories)
   - Specify the JSON file path (default is the Sympla C4 diagrams repository)
   - Set the minimum number of links required for a repository to be considered "in order"
   - Upload a CSV file containing critical repository information

2. **Main Working Area**:
   - View all mapped C4 elements in a grid
   - See which elements have documentation links (repository, logs, APM, openAPI, monitor, dashboard, backstage)
   - Track progress of critical repositories
   - View overall documentation completeness

3. **CSV Format**:
   The CSV file should contain at least a column named "url" with repository URLs.

## Example CSV Format

```
name,url,team
Repository 1,https://gitlab.com/sympla/repo1,Team A
Repository 2,https://gitlab.com/sympla/repo2,Team B
```

## Notes

- The application stores settings in the session state, so they persist during your session
- Repository URLs are normalized for comparison between C4 elements and CSV data
- Progress is calculated based on the number of documentation links present vs. the minimum required 