import streamlit as st
import pandas as pd
import requests
import json
import os
import re
from urllib.parse import urlparse
import plotly.express as px
import plotly.graph_objects as go
import matplotlib.pyplot as plt
import altair as alt
import streamlit.components.v1 as components
from datetime import datetime

# Set page configuration
st.set_page_config(
    page_title="C4 Repository Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main .block-container {
        padding-top: 2rem;
    }
    .stProgress > div > div > div > div {
        background-color: #4CAF50;
    }
    .stDataFrame {
        margin-top: 1rem;
    }
    .sidebar .block-container {
        padding-top: 2rem;
    }
    h1, h2, h3 {
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# File to store settings
SETTINGS_FILE = "c4_analytics_settings.json"

def load_settings():
    """Load saved settings from file if it exists"""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                settings = json.load(f)
                return settings
        except Exception as e:
            st.error(f"Error loading settings: {e}")
    # Default values without token
    return {
        "project_id": "67327904",
        "file_path": "likec4.json",
        "branch": "main",
        "selected_links": ["repository", "logs", "APM", "openAPI", "monitor", "dashboard"]
    }

def save_settings(project_id, file_path, branch, selected_links):
    """Save current settings to file"""
    settings = {
        "project_id": project_id,
        "file_path": file_path,
        "branch": branch,
        "selected_links": selected_links,
        "last_saved": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f)
        return True
    except Exception as e:
        st.error(f"Error saving settings: {e}")
        return False

def clear_settings():
    """Clear all saved settings"""
    if os.path.exists(SETTINGS_FILE):
        try:
            os.remove(SETTINGS_FILE)
            return True
        except Exception as e:
            st.error(f"Error clearing settings: {e}")
            return False
    return True  # Return True if file doesn't exist (nothing to clear)

# Initialize session state variables
if 'settings_loaded' not in st.session_state:
    settings = load_settings()
    st.session_state.gitlab_token = ""  # Initialize with empty string for security
    st.session_state.project_id = settings.get("project_id", "67327904")
    st.session_state.file_path = settings.get("file_path", "likec4.json")
    st.session_state.branch = settings.get("branch", "main")
    st.session_state.selected_links = settings.get("selected_links", ["repository", "logs", "APM", "openAPI", "monitor", "dashboard"])
    st.session_state.settings_loaded = True

# Initialize other session state variables if they don't exist
if 'gitlab_token' not in st.session_state:
    st.session_state.gitlab_token = ""

if 'selected_links' not in st.session_state:
    st.session_state.selected_links = ["repository", "logs", "APM", "openAPI", "monitor", "dashboard"]

if 'mapped_elements' not in st.session_state:
    st.session_state.mapped_elements = []

if 'c4_data' not in st.session_state:
    st.session_state.c4_data = None

if 'csv_data' not in st.session_state:
    st.session_state.csv_data = None

if 'critical_repos' not in st.session_state:
    st.session_state.critical_repos = []

# Add JavaScript to load settings from localStorage on page load
components.html(
    """
    <script>
    function loadSettings() {
        const savedSettings = localStorage.getItem('c4_analytics_settings');
        if (savedSettings) {
            try {
                const settings = JSON.parse(savedSettings);
                console.log('Found saved settings:', settings);
                
                // Update session state via query parameters
                const params = new URLSearchParams(window.location.search);
                let needsReload = false;
                
                if (settings.project_id && !params.has('project_id')) {
                    params.set('project_id', settings.project_id);
                    needsReload = true;
                }
                if (settings.file_path && !params.has('file_path')) {
                    params.set('file_path', settings.file_path);
                    needsReload = true;
                }
                if (settings.branch && !params.has('branch')) {
                    params.set('branch', settings.branch);
                    needsReload = true;
                }
                if (settings.selected_links && !params.has('selected_links')) {
                    params.set('selected_links', JSON.stringify(settings.selected_links));
                    needsReload = true;
                }
                
                if (needsReload) {
                    // Reload the page with the new query parameters
                    window.location.search = params.toString();
                }
            } catch (e) {
                console.error('Error loading settings from localStorage:', e);
            }
        }
    }
    
    // Run immediately and also when DOM is fully loaded
    loadSettings();
    if (document.readyState !== 'complete') {
        window.addEventListener('load', loadSettings);
    }
    </script>
    """,
    height=0,
)

# Read query parameters to initialize session state from localStorage
# Using the new st.query_params API instead of the deprecated experimental version
if st.query_params:
    if 'project_id' in st.query_params:
        st.session_state.project_id = st.query_params['project_id']
    if 'file_path' in st.query_params:
        st.session_state.file_path = st.query_params['file_path']
    if 'branch' in st.query_params:
        st.session_state.branch = st.query_params['branch']
    if 'selected_links' in st.query_params:
        try:
            st.session_state.selected_links = json.loads(st.query_params['selected_links'])
        except ValueError:
            pass  # Keep default if conversion fails

# Function to fetch JSON data from GitLab
def fetch_gitlab_json(url=None, token=None, project_id=None, file_path=None, branch=None):
    # If direct URL is provided, use it
    if url:
        headers = {}
        if token:
            headers['PRIVATE-TOKEN'] = token
        else:
            st.warning("No GitLab token provided. You may encounter authentication issues when accessing private repositories.")
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                st.error("Authentication error: You need a valid GitLab token to access this resource. Please provide a valid token in the sidebar.")
            else:
                st.error(f"HTTP Error: {str(e)}")
            return None
        except Exception as e:
            st.error(f"Error fetching JSON data: {str(e)}")
            return None
    
    # If project_id, file_path and branch are provided, construct API URL
    elif project_id and file_path:
        branch = branch or "main"  # Default to main branch if not specified
        
        # URL encode the file path
        encoded_file_path = requests.utils.quote(file_path, safe='')
        api_url = f"https://gitlab.com/api/v4/projects/{project_id}/repository/files/{encoded_file_path}/raw?ref={branch}"
        
        headers = {}
        if token:
            headers['PRIVATE-TOKEN'] = token
        else:
            st.warning("No GitLab token provided. You may encounter authentication issues when accessing private repositories.")
        
        try:
            response = requests.get(api_url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                st.error("Authentication error: You need a valid GitLab token to access this resource. Please provide a valid token in the sidebar.")
            else:
                st.error(f"HTTP Error: {str(e)}")
            return None
        except Exception as e:
            st.error(f"Error fetching JSON data: {str(e)}")
            return None
    
    else:
        st.error("Either direct URL or project ID and file path must be provided.")
        return None

# Function to extract elements of specific kinds from C4 data
def extract_elements(c4_data, target_kinds):
    elements = []
    
    # Check if the JSON structure has elements at the top level
    if c4_data and 'elements' in c4_data:
        for element_id, element_data in c4_data['elements'].items():
            # Check if the element has the kind we're looking for
            if 'kind' in element_data and element_data['kind'] in target_kinds:
                # Add element ID to the data for reference
                element_data['id'] = element_id
                elements.append(element_data)
    # Also check the alternative structure (elements under specification)
    elif c4_data and 'specification' in c4_data and 'elements' in c4_data['specification']:
        for element_id, element_data in c4_data['specification']['elements'].items():
            # Check if the element has the kind we're looking for
            if 'kind' in element_data and element_data['kind'] in target_kinds:
                # Add element ID to the data for reference
                element_data['id'] = element_id
                elements.append(element_data)
    
    return elements

# Function to check if an element has specific links
def check_element_links(element, link_types):
    result = {link_type: False for link_type in link_types}
    
    if 'links' in element and element['links']:
        for link in element['links']:
            if 'title' in link and link['title'] in link_types:
                result[link['title']] = True
    
    return result

# Function to extract repository URL from element links
def get_repository_url(element):
    if 'links' in element and element['links']:
        for link in element['links']:
            if 'title' in link and link['title'] == 'repository' and 'url' in link:
                return link['url']
    return None

# Function to match repository URLs between C4 elements and CSV data
def match_repositories(elements, csv_data):
    if csv_data is None or elements is None:
        return []
    
    # Make column names case-insensitive by finding the URL column
    url_column = None
    for column in csv_data.columns:
        if column.lower() == 'url':
            url_column = column
            break
    
    # If no URL column found, show a warning
    if url_column is None:
        st.warning("No 'url' column found in CSV. Please ensure your CSV has a column named 'url', 'URL', or similar.")
        return []
    
    # Extract repository URLs from elements
    element_repos = {}
    for element in elements:
        repo_url = get_repository_url(element)
        if repo_url:
            # Normalize URL for comparison
            parsed_url = urlparse(repo_url)
            normalized_url = f"{parsed_url.netloc}{parsed_url.path}".rstrip('/').lower()  # Convert to lowercase
            element_repos[normalized_url] = element
    
    # Match with CSV repositories
    matches = []
    for _, row in csv_data.iterrows():
        if url_column in row and row[url_column]:
            # Normalize URL for comparison
            parsed_url = urlparse(str(row[url_column]))
            normalized_url = f"{parsed_url.netloc}{parsed_url.path}".rstrip('/').lower()  # Convert to lowercase
            
            if normalized_url in element_repos:
                matches.append({
                    'csv_repo': row,
                    'c4_element': element_repos[normalized_url]
                })
    
    return matches

# Sidebar for setup
with st.sidebar:
    st.title("Setup")
    
    # Create tabs for different configuration sections
    gitlab_tab, csv_tab, progress_tab = st.tabs(["GitLab Configuration", "Repository CSV", "Progress Settings"])
    
    # GitLab configuration tab
    with gitlab_tab:
        st.markdown("In this area you can configure the GitLab API (or upload a local file) to fetch the C4 data published in the [repository](https://gitlab.com/sympla/bed-of-rock/sympla-c4-diagrams/).")

        # GitLab credentials
        st.header("GitLab Credentials")
        gitlab_token = st.text_input(
            "GitLab Token (required for private repositories)", 
            value=st.session_state.gitlab_token,
            type="password",
            help="Generate a personal access token in GitLab with 'read_api' scope"
        )
        
        # JSON file path
        st.header("C4 JSON File")
        json_source = st.radio("JSON Source", ["GitLab API", "Local File"])

        if json_source == "GitLab API":
            project_id = st.text_input(
                "GitLab Project ID",
                value=st.session_state.project_id,
                help="The numeric ID or 'namespace/project-name' of your GitLab project"
            )
            file_path = st.text_input(
                "File Path",
                value=st.session_state.file_path,
                help="Path to the JSON file in the repository"
            )
            branch = st.text_input(
                "Branch",
                value=st.session_state.branch,
                help="Branch name (defaults to 'main')"
            )
            
            # Fetch data button
            if st.button("Fetch Data from GitLab API"):
                with st.spinner("Fetching C4 data..."):
                    c4_data = fetch_gitlab_json(
                        token=gitlab_token,  # Use the current value, not session_state
                        project_id=project_id,
                        file_path=file_path,
                        branch=branch
                    )
                    if c4_data:
                        st.session_state.c4_data = c4_data
                        target_kinds = ['container', 'application', 'service', 'webapp', 'mobile']
                        st.session_state.mapped_elements = extract_elements(c4_data, target_kinds)
                        st.success(f"Successfully fetched {len(st.session_state.mapped_elements)} elements!")
                        
                        # Save settings when successfully fetching data
                        st.session_state.gitlab_token = gitlab_token
                        st.session_state.project_id = project_id
                        st.session_state.file_path = file_path
                        st.session_state.branch = branch
                        
                        # Save to localStorage
                        save_settings_js = f"""
                        <script>
                            const settings = {{
                                gitlab_token: "{gitlab_token}",
                                project_id: "{project_id}",
                                file_path: "{file_path}",
                                branch: "{branch}",
                                selected_links: {json.dumps(st.session_state.selected_links)}
                            }};
                            localStorage.setItem('c4_analytics_settings', JSON.stringify(settings));
                            console.log('Settings saved automatically after successful fetch');
                        </script>
                        """
                        st.components.v1.html(save_settings_js, height=0)
                    else:
                        st.error("Failed to fetch C4 data.")
        else:
            uploaded_json = st.file_uploader("Upload JSON File", type=["json"])
            if uploaded_json is not None:
                # Read and parse the uploaded JSON file
                try:
                    json_content = uploaded_json.read()
                    c4_data = json.loads(json_content)
                    st.session_state.c4_data = c4_data
                    
                    # Add debugging information
                    st.expander("JSON Structure Debug").write({
                        "Top level keys": list(c4_data.keys()),
                        "Has 'elements' key": 'elements' in c4_data,
                        "Has 'specification' key": 'specification' in c4_data,
                        "Has 'specification.elements'": 'specification' in c4_data and 'elements' in c4_data.get('specification', {})
                    })
                    
                    target_kinds = ['container', 'application', 'service', 'webapp', 'mobile']
                    st.session_state.mapped_elements = extract_elements(c4_data, target_kinds)
                    
                    if len(st.session_state.mapped_elements) > 0:
                        st.success(f"Successfully loaded {len(st.session_state.mapped_elements)} elements!")
                    else:
                        st.warning("No elements of the target kinds were found in the JSON file.")
                        # Show sample of the data structure to help debug
                        with st.expander("JSON Data Sample"):
                            if 'elements' in c4_data:
                                sample_elements = list(c4_data['elements'].items())[:3]
                                st.json(dict(sample_elements))
                            elif 'specification' in c4_data and 'elements' in c4_data['specification']:
                                sample_elements = list(c4_data['specification']['elements'].items())[:3]
                                st.json(dict(sample_elements))
                            else:
                                st.write("Could not find elements in the expected structure.")
                                st.json({k: type(v).__name__ for k, v in c4_data.items()})
                except Exception as e:
                    st.error(f"Error parsing JSON file: {str(e)}")
    
    # CSV repositories configuration tab
    with csv_tab:
        st.markdown("In this area you can upload a CSV file with the critical repositories of Sympla of your interest.")
        
        # Add CSV file upload
        st.header("Repository CSV")
        csv_file = st.file_uploader(
            "Upload CSV with repository information",
            type=["csv"],
            help="CSV should contain a column with repository URLs"
        )

        st.info("""
        **Where I could find this the CSV file?:**
        You can generate the CSV file in the [dashboard](https://sympla.gitlab.io/bed-of-rock/sympla-repositories-analyzer/c4-critical) in the section "C4-critical".
        """)
        
        # Process CSV if uploaded
        if csv_file is not None:
            try:
                csv_data = pd.read_csv(csv_file)
                st.session_state.csv_data = csv_data
                st.sidebar.success(f"CSV loaded with {len(csv_data)} repositories!")
            except Exception as e:
                st.sidebar.error(f"Error loading CSV: {str(e)}")
    
    with progress_tab:
        # Progress Settings
        st.header("Progress Settings")
        
        # Define all possible link types
        all_link_types = ["repository", "logs", "APM", "openAPI", "monitor", "monitoring", "dashboard", "backstage"]
        
        # Let user select which links to include in progress calculation
        selected_links = st.multiselect(
            "Select links to evaluate for progress:",
            options=all_link_types,
            default=st.session_state.selected_links,
            help="Progress will be calculated based on the presence of these links"
        )
        
        # Show explanation of how progress is calculated
        st.info("""
        **How progress is calculated:**
        - Each repository is checked for the selected links
        - Progress percentage = (Number of present links / Total selected links) × 100%
        - A repository is considered "Complete" when all selected links are present
        """)

    # Add a separator
    st.markdown("---")
    
    # Create two columns for the buttons
    col1, col2 = st.sidebar.columns(2)

    with col1:
        # Save settings button
        if st.button("💾 Save Settings", use_container_width=True):
            # Update session state variables
            st.session_state.gitlab_token = gitlab_token  # Update session state but don't save to file
            st.session_state.selected_links = selected_links
            
            if json_source == "GitLab API":
                st.session_state.project_id = project_id
                st.session_state.file_path = file_path
                st.session_state.branch = branch
            
            # Save settings to file (excluding token)
            if save_settings(
                project_id=project_id,
                file_path=file_path,
                branch=branch,
                selected_links=selected_links
            ):
                # Save non-sensitive settings to localStorage
                settings_js = f"""
                <script>
                    try {{
                        const settings = {{
                            project_id: "{project_id}",
                            file_path: "{file_path}",
                            branch: "{branch}",
                            selected_links: {json.dumps(selected_links)}
                        }};
                        localStorage.setItem('c4_analytics_settings', JSON.stringify(settings));
                        console.log('Settings saved successfully');
                    }} catch (e) {{
                        console.error('Error saving settings:', e);
                    }}
                </script>
                """
                st.components.v1.html(settings_js, height=0)
                st.success("Settings saved successfully!")
            else:
                st.error("Failed to save settings.")

    with col2:
        # Clear settings button
        if st.button("🗑️ Clear Settings", use_container_width=True):
            if clear_settings():
                # Reset session state to defaults
                st.session_state.gitlab_token = ""
                st.session_state.project_id = "67327904"
                st.session_state.file_path = "likec4.json"
                st.session_state.branch = "main"
                st.session_state.selected_links = ["repository", "logs", "APM", "openAPI", "monitor", "dashboard"]
                st.success("Settings cleared!")
                # Force a rerun to update the UI
                st.rerun()
            else:
                st.error("Failed to clear settings.")

# Main content area
st.title("C4 Repository Analytics")
st.markdown("""
This tool is designed to help you analyze the C4 diagrams published in the [repository](https://gitlab.com/sympla/bed-of-rock/sympla-c4-diagrams/). 
The repository serves as the foundation for Sympla's architecture portal with the following features:

- **Architecture as Code**: Version-controlled diagrams reviewed through pull requests
- **GitLab Pages Hosting**: Making the portal accessible to all teams
- **Easy Contribution**: Using the LikeC4 VSCode extension for diagram creation and editing
- **Diagram Export**: Ability to export diagrams to PNG, SVG, and other formats
""")

# Calculate days remaining for each milestone
today = datetime.now().date()
milestone1_date = datetime(2025, 3, 15).date()
milestone2_date = datetime(2025, 5, 1).date()
milestone3_date = datetime(2025, 6, 1).date()

days_to_milestone1 = (milestone1_date - today).days
days_to_milestone2 = (milestone2_date - today).days
days_to_milestone3 = (milestone3_date - today).days

# Create milestone progress section
st.subheader("Implementation Milestones")

# Create three columns for the milestones
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="Milestone 1: 10% Coverage", 
        value=f"{days_to_milestone1} days remaining",
        delta="March 15, 2025",
        delta_color="off"
    )

with col2:
    st.metric(
        label="Milestone 2: 50% Coverage", 
        value=f"{days_to_milestone2} days remaining",
        delta="May 1, 2025",
        delta_color="off"
    )

with col3:
    st.metric(
        label="Milestone 3: 100% Coverage", 
        value=f"{days_to_milestone3} days remaining",
        delta="June 1, 2025",
        delta_color="off"
    )

# Display elements in a grid with filters
if st.session_state.mapped_elements:
    st.header(f"Mapped C4 Elements ({len(st.session_state.mapped_elements)})")
    
    # Create filter controls in expandable section
    with st.expander("Filter C4 Elements", expanded=False):
        # Create two columns for filters
        filter_col1, filter_col2 = st.columns(2)
        
        with filter_col1:
            # Filter by element kind
            kinds = sorted(set(element.get('kind', '') for element in st.session_state.mapped_elements))
            selected_kinds = st.multiselect(
                "Filter by Kind",
                options=kinds,
                default=kinds
            )
            
            # Filter by technology
            technologies = sorted(set(element.get('technology', '') for element in st.session_state.mapped_elements 
                                if element.get('technology')))
            selected_technologies = st.multiselect(
                "Filter by Technology",
                options=technologies,
                default=[]
            )
        
        with filter_col2:
            # Filter by link presence
            link_types = ['repository', 'logs', 'APM', 'openAPI', 'monitor', 'dashboard', 'backstage']
            link_filter_options = ["Any", "Has Link", "Missing Link"]
            link_filters = {}
            
            for link_type in link_types:
                link_filters[link_type] = st.selectbox(
                    f"Filter by {link_type}",
                    options=link_filter_options,
                    index=0  # Default to "Any"
                )
    
    # Prepare data for the grid
    grid_data = []
    link_types = ['repository', 'logs', 'APM', 'openAPI', 'monitor', 'monitoring', 'dashboard', 'backstage']
    
    for element in st.session_state.mapped_elements:
        # Apply kind filter
        if element.get('kind', '') not in selected_kinds:
            continue
            
        # Apply technology filter
        if selected_technologies and element.get('technology', '') not in selected_technologies:
            continue
        
        # Get basic element info
        element_info = {
            'kind': element.get('kind', ''),
            'title': element.get('title', ''),
            'technology': element.get('technology', ''),
            'description': element.get('description', '')
        }
        
        # Check for links
        link_info = check_element_links(element, link_types)
        
        # Apply link filters
        skip_element = False
        for link_type, filter_value in link_filters.items():
            if link_type in link_info:
                if filter_value == "Has Link" and not link_info[link_type]:
                    skip_element = True
                    break
                elif filter_value == "Missing Link" and link_info[link_type]:
                    skip_element = True
                    break
        
        if skip_element:
            continue
            
        # Combine all info
        row_data = {**element_info, **link_info}
        grid_data.append(row_data)
    
    # Convert to DataFrame for display
    if grid_data:
        df = pd.DataFrame(grid_data)
        
        # Replace monitoring with monitor if monitor is False and monitoring is True
        if 'monitoring' in df.columns and 'monitor' in df.columns:
            df['monitor'] = df.apply(lambda row: True if row['monitoring'] else row['monitor'], axis=1)
            df = df.drop('monitoring', axis=1)
        
        # Reorder columns
        column_order = ['kind', 'title', 'technology', 'description', 'repository', 
                        'logs', 'APM', 'openAPI', 'monitor', 'dashboard', 'backstage']
        df = df[[col for col in column_order if col in df.columns]]
        
        # Display the grid with count of filtered elements
        st.subheader(f"Showing {len(df)} of {len(st.session_state.mapped_elements)} elements")
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No elements match the selected filters.")

# Critical repositories progress with filters
if st.session_state.csv_data is not None and len(st.session_state.mapped_elements) > 0:
    st.header("Critical Repositories Progress")
    
    # Match repositories
    matches = match_repositories(st.session_state.mapped_elements, st.session_state.csv_data)
    st.session_state.critical_repos = matches
    
    # Get all repositories from CSV
    all_repos = st.session_state.csv_data
    total_repos = len(all_repos)
    
    if total_repos > 0:
        # Calculate progress for matched repositories
        progress_data = []
        matched_repo_urls = set()
        
        for match in matches:
            element = match['c4_element']
            repo_url = get_repository_url(element)
            csv_repo_url = match['csv_repo'].get('url', '')
            matched_repo_urls.add(csv_repo_url)
            
            # Check links
            link_info = check_element_links(element, st.session_state.selected_links)
            
            # Count true values (if monitoring is true, count it as monitor)
            if 'monitoring' in link_info and link_info['monitoring'] and 'monitor' in st.session_state.selected_links:
                link_info['monitor'] = True
            
            # Count links that are present
            present_links = sum(1 for link_type, has_link in link_info.items() 
                              if has_link and link_type in st.session_state.selected_links)
            
            # Total number of selected links
            total_selected = len(st.session_state.selected_links)
            
            # Calculate progress percentage
            progress_pct = (present_links / total_selected) * 100 if total_selected > 0 else 0
            
            # Add to progress data
            progress_data.append({
                'Repository': csv_repo_url,
                'Element': element.get('title', ''),
                'Links': f"{present_links}/{total_selected}",
                'Progress': progress_pct,
                'Progress %': f"{progress_pct:.1f}%",
                'Status': 'Complete' if present_links == total_selected else 'Incomplete'
            })
        
        # Find the URL column first
        url_column = None
        for column in all_repos.columns:
            if column.lower() == 'url':
                url_column = column
                break

        if url_column:
            # Add unmatched repositories with 0 progress
            for _, repo_row in all_repos.iterrows():
                repo_url = repo_row.get(url_column, '')
                if repo_url and repo_url not in matched_repo_urls:
                    progress_data.append({
                        'Repository': repo_url,
                        'Element': 'Not mapped in C4',
                        'Links': '0/0',
                        'Progress': 0,
                        'Progress %': "0.0%",
                        'Status': 'Not mapped'
                    })
        else:
            st.warning("No 'url' column found in CSV. Cannot identify unmatched repositories.")
        
        # Convert to DataFrame
        progress_df = pd.DataFrame(progress_data)
        
        # Add filters for repository progress
        with st.expander("Filter Repositories", expanded=False):
            # Create two columns for filters
            repo_filter_col1, repo_filter_col2 = st.columns(2)
            
            with repo_filter_col1:
                # Filter by status
                status_options = ['All', 'Complete', 'Incomplete', 'Not mapped']
                selected_status = st.selectbox(
                    "Filter by Status",
                    options=status_options,
                    index=0  # Default to "All"
                )
                
                # Filter by progress range
                min_progress, max_progress = st.slider(
                    "Progress Range (%)",
                    min_value=0,
                    max_value=100,
                    value=(0, 100)
                )
            
            with repo_filter_col2:
                # Search by repository URL
                search_term = st.text_input(
                    "Search by Repository URL",
                    placeholder="Enter part of URL..."
                )
                
                # Search by element name
                element_search = st.text_input(
                    "Search by Element Name",
                    placeholder="Enter part of element name..."
                )
        
        # Apply filters to progress_df
        filtered_df = progress_df.copy()
        
        # Status filter
        if selected_status != 'All':
            filtered_df = filtered_df[filtered_df['Status'] == selected_status]
        
        # Progress range filter
        if 'Progress' in filtered_df.columns:
            filtered_df = filtered_df[(filtered_df['Progress'] >= min_progress) & 
                                     (filtered_df['Progress'] <= max_progress)]
        else:
            # If 'Progress' column doesn't exist, try to find the correct column
            # or create it from 'Progress %' if it exists
            if 'Progress %' in filtered_df.columns:
                # Extract numeric values from 'Progress %' column
                filtered_df['Progress'] = filtered_df['Progress %'].str.rstrip('%').astype(float)
            else:
                # If neither column exists, add a default Progress column
                st.warning("Progress column not found. Adding default values.")
                filtered_df['Progress'] = 0.0
            
            # Now apply the filter
            filtered_df = filtered_df[(filtered_df['Progress'] >= min_progress) & 
                                     (filtered_df['Progress'] <= max_progress)]
        
        # Repository URL search
        if search_term:
            filtered_df = filtered_df[filtered_df['Repository'].str.contains(search_term, case=False, na=False)]
        
        # Element name search
        if element_search:
            filtered_df = filtered_df[filtered_df['Element'].str.contains(element_search, case=False, na=False)]
        
        # Calculate overall progress based on ALL repositories in CSV
        complete_repos = sum(1 for p in progress_data if p['Status'] == 'Complete')
        incomplete_repos = sum(1 for p in progress_data if p['Status'] == 'Incomplete')
        unmapped_repos = sum(1 for p in progress_data if p['Status'] == 'Not mapped')
        
        overall_progress = (complete_repos / total_repos) * 100 if total_repos > 0 else 0

        # Display overall progress with percentage
        st.subheader(f"Overall Progress: {complete_repos}/{total_repos} repositories ({overall_progress:.1f}%)")
        st.progress(overall_progress / 100)
        
        # Display progress for each repository
        st.subheader(f"Repository Details (Showing {len(filtered_df)} of {len(progress_df)} repositories)")
        
        # Sort by progress (descending)
        filtered_df = filtered_df.sort_values('Progress', ascending=False)
        
        # Add visual indicators for status
        def format_status(status):
            if status == 'Complete':
                return f"✅ {status}"
            elif status == 'Incomplete':
                return f"⚠️ {status}"
            else:
                return f"❌ {status}"
        
        # Create a copy with formatted columns
        display_df = filtered_df.copy()
        if 'Status' in display_df.columns:
            display_df['Status'] = display_df['Status'].apply(format_status)
        else:
            # If Status column doesn't exist, create it with a default value
            st.warning("Status column not found in the data. Adding default values.")
            display_df['Status'] = "❓ Unknown"
        
        # Before displaying the dataframe, ensure all required columns exist
        required_columns = ['Repository', 'Element', 'Links', 'Progress', 'Status']
        for col in required_columns:
            if col not in display_df.columns:
                if col == 'Progress':
                    display_df[col] = 0.0
                elif col == 'Links':
                    display_df[col] = "0/0"
                elif col == 'Element':
                    display_df[col] = "Unknown"
                elif col == 'Status':
                    display_df[col] = "❓ Unknown"
                else:
                    display_df[col] = ""
        
        # Now create the Progress_Numeric column
        display_df['Progress_Numeric'] = display_df['Progress']
        
        st.dataframe(
            display_df[['Repository', 'Element', 'Links', 'Progress_Numeric', 'Status']], 
            use_container_width=True,
            column_config={
                "Repository": st.column_config.TextColumn("Repository URL", width="medium"),
                "Element": st.column_config.TextColumn("C4 Element", width="medium"),
                "Links": st.column_config.TextColumn("Links Count"),
                "Progress_Numeric": st.column_config.ProgressColumn(
                    "Progress", 
                    min_value=0, 
                    max_value=100,
                    format="%.0f"  # Format is valid for ProgressColumn
                ),
                "Status": st.column_config.TextColumn("Status", width="small")
            }
        )

        # Add visualization section
        st.header("Progress Visualization")

        # Calculate counts for each status
        if 'progress_df' in locals() and not progress_df.empty:
            complete_count = sum(1 for p in progress_data if p['Status'] == 'Complete')
            incomplete_count = sum(1 for p in progress_data if p['Status'] == 'Incomplete')
            not_mapped_count = sum(1 for p in progress_data if p['Status'] == 'Not mapped')
            
            # Create data for pie chart
            labels = ['Complete', 'Incomplete', 'Not Mapped']
            values = [complete_count, incomplete_count, not_mapped_count]
            colors = ['#4CAF50', '#FFC107', '#F44336']  # Green, Amber, Red
            
            # Create two columns for charts
            chart_col1, chart_col2 = st.columns([3, 2])
            
            with chart_col1:
                # Create pie chart
                fig_pie = go.Figure(data=[go.Pie(
                    labels=labels,
                    values=values,
                    hole=.4,  # Donut chart
                    marker_colors=colors,
                    textinfo='label+percent',
                    insidetextorientation='radial'
                )])
                
                fig_pie.update_layout(
                    title_text="Repository Status Distribution",
                    showlegend=True,
                    legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
                    margin=dict(t=50, b=50, l=10, r=10),
                    height=400
                )
                
                st.plotly_chart(fig_pie, use_container_width=True)
            
            with chart_col2:
                # Create bar chart showing progress by status
                status_progress = progress_df.groupby('Status')['Progress'].mean().reset_index()
                
                # Ensure all statuses are present
                all_statuses = pd.DataFrame({'Status': labels})
                status_progress = pd.merge(all_statuses, status_progress, on='Status', how='left').fillna(0)
                
                # Create horizontal bar chart
                fig_bar = go.Figure()
                
                # Add bars
                for i, (status, avg_progress) in enumerate(zip(status_progress['Status'], status_progress['Progress'])):
                    fig_bar.add_trace(go.Bar(
                        y=[status],
                        x=[avg_progress],
                        orientation='h',
                        name=status,
                        marker_color=colors[i],
                        text=[f"{avg_progress:.1f}%"],
                        textposition='auto'
                    ))
                
                fig_bar.update_layout(
                    title_text="Average Progress by Status",
                    xaxis_title="Progress (%)",
                    yaxis=dict(
                        title="Status",
                        categoryorder='array',
                        categoryarray=['Complete', 'Incomplete', 'Not Mapped']
                    ),
                    margin=dict(t=50, b=50, l=10, r=10),
                    height=400,
                    showlegend=False
                )
                
                fig_bar.update_xaxes(range=[0, 100])
                
                st.plotly_chart(fig_bar, use_container_width=True)
            
            # Add a progress over time chart (simulated since we don't have historical data)
            st.subheader("Repository Completion Progress")
            
            # Create a gauge chart to show overall completion
            overall_progress = (complete_count / total_repos) * 100 if total_repos > 0 else 0
            
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number",
                value=overall_progress,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "Overall Completion"},
                gauge={
                    'axis': {'range': [0, 100]},
                    'bar': {'color': "#4CAF50"},
                    'steps': [
                        {'range': [0, 33], 'color': "#FFCDD2"},
                        {'range': [33, 66], 'color': "#FFE082"},
                        {'range': [66, 100], 'color': "#C8E6C9"}
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': 90
                    }
                }
            ))
            
            fig_gauge.update_layout(
                height=300,
                margin=dict(t=50, b=0, l=25, r=25)
            )
            
            st.plotly_chart(fig_gauge, use_container_width=True)
            
            # Add a summary metrics row
            st.subheader("Summary Metrics")
            
            metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
            
            with metric_col1:
                st.metric(
                    label="Total Repositories", 
                    value=total_repos
                )
            
            with metric_col2:
                st.metric(
                    label="Complete", 
                    value=complete_count,
                    delta=f"{(complete_count/total_repos*100):.1f}%" if total_repos > 0 else "0%"
                )
            
            with metric_col3:
                st.metric(
                    label="Incomplete", 
                    value=incomplete_count,
                    delta=f"{(incomplete_count/total_repos*100):.1f}%" if total_repos > 0 else "0%",
                    delta_color="inverse"
                )
            
            with metric_col4:
                st.metric(
                    label="Not Mapped", 
                    value=not_mapped_count,
                    delta=f"{(not_mapped_count/total_repos*100):.1f}%" if total_repos > 0 else "0%",
                    delta_color="inverse"
                )
        else:
            st.info("Upload a CSV file and fetch C4 data to see visualizations.")

        # Add recommendations section
        st.header("Recommendations")
        
        # Calculate which repositories need the most attention
        if not progress_df.empty:
            # Filter to incomplete repositories
            incomplete_df = progress_df[progress_df['Status'] == 'Incomplete'].copy()
            
            if not incomplete_df.empty:
                # Sort by progress (ascending)
                incomplete_df = incomplete_df.sort_values('Progress')
                
                # Get top 5 repositories that need attention
                attention_needed = incomplete_df.head(5)
                
                st.subheader("Repositories Needing Attention")
                for _, repo in attention_needed.iterrows():
                    st.markdown(f"""
                    **{repo['Element']}** ({repo['Progress']:.1f}% complete)
                    - Repository: {repo['Repository']}
                    - Current links: {repo['Links']} of {len(st.session_state.selected_links)} selected
                    - Missing: {len(st.session_state.selected_links) - len(repo['Links'].split('/'))} links
                    """)
            
            # Unmapped repositories
            unmapped_df = progress_df[progress_df['Status'] == 'Not mapped']
            if not unmapped_df.empty:
                st.subheader("Unmapped Repositories")
                st.markdown(f"**{len(unmapped_df)}** critical repositories are not mapped in the C4 diagrams:")
                for _, repo in unmapped_df.head(5).iterrows():
                    st.markdown(f"- {repo['Repository']}")
                
                if len(unmapped_df) > 5:
                    st.markdown(f"... and {len(unmapped_df) - 5} more")
    else:
        st.info("No repositories found in the CSV file.")
else:
    if st.session_state.csv_data is None:
        st.info("Please upload a CSV file with repository information.")
    if not st.session_state.mapped_elements or len(st.session_state.mapped_elements) == 0:
        st.info("Please fetch C4 data to see repository progress.")

# Footer
st.markdown("---")
st.markdown("C4 Repository Analytics Tool | Developed for Sympla") 