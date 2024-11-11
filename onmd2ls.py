import re
import time
import os
from datetime import datetime
import argparse
import shutil

def transform_file_paths(text, updated_date, docformat):
    """
    Used to rename image files to match the naming conventions in Logseq 
    which include the modified date at the end of the filename

    :param text: original text where patterns are extracted from
    :param updated_date: new date to be used for concatenation
    :type updated_date: date string extracted from OneNote (it will be converted)
    :param docformat: whether the MD files were produced using onenote-md-exporter or ConvertOneNoteToMarkDown

    :return:
        - transformed text with new file paths included
        - a list of tuples containing asset file names (including new names) to be copied
    """

    if (updated_date == None):
        updated_date = datetime.datetime.now()

    # Parse the string to a datetime object
    if docformat == 'onenote-md-exporter':
        dt = datetime.strptime(updated_date, "%Y-%m-%dT%H:%M:%S")
    elif docformat == 'ConvertOneNoteToMarkDown':
        dt = datetime.strptime(updated_date, "%Y-%m-%d %H:%M:%S %z")

    # Convert to a Unix timestamp (seconds since January 1, 1970)
    timestamp = int(time.mktime(dt.timetuple()))

    # List to store mv commands
    #renimg_commands = []
    assets = []
     
    # Function to replace matched patterns and generate mv commands
    def replace_path(match):
        original_filename = f"{match.group(1)}.{match.group(2)}"
        new_filename = f"{match.group(1)}_{timestamp}.{match.group(2)}"
        #renimg_commands.append(f"cp {original_filename} ./renimg/{new_filename}")
        assets.append((original_filename, new_filename))
        return f"(../assets/{new_filename})"
       
    # Regex pattern to match the specified format
    pattern = r'\(../../resources/(\w+)\.(\w+)\)'
    
    # Replace all occurrences of the pattern in the text
    transformed_text = re.sub(pattern, replace_path, text)
    
    return transformed_text, assets

def add_trailing_slash(path):
    """
    Add a trailing slash (/) to a path if missing
    Used so that a file name can be contenated 

    :param path: path to modify
    :return: path with slash at the end
    """

    # Check if the path already ends with a slash
    if not path.endswith(os.path.sep):
        return path + os.path.sep
    return path

def create_folder_if_not_exists(folder_path):
    """
    Create the folder if it doesn't exist

    :param folder_path: path to modify
    :return: path with slash at the end
    """

    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

def parse_bool(value):
    """
    Parse script argument

    :param value: the passed argument
    :return: True or False depending argument
    """
    if isinstance(value, str):
        value = value.lower()
        if value in ('true', '1', 't', 'y', 'yes'):
            return True
        elif value in ('false', '0', 'f', 'n', 'no'):
            return False
    raise argparse.ArgumentTypeError(f"Invalid value for boolean conversion: '{value}'")


def process_metadata_segment(text, add_property_metadata, docformat):
    """
    Extract the page title, update and created dates (usually in the header)
    Add back in the format of Logseq properties and also return in structured form

    :param text: original text where metadata is to be extracted from
    :param add_property_metadata: whether to add metadata fields (created/updated dates) as properties\
    :param docformat: whether the MD files were produced using onenote-md-exporter or ConvertOneNoteToMarkDown

    :return:
        - transformed text with new metadata block
        - metadata block array
        - title string
        - created date
        - updated date
    """

    # Regex pattern to match the segment and extract values
    if docformat == 'onenote-md-exporter':
        pattern_meta = r'---\ntitle: (.*)\nupdated: (.*)\ncreated: (.*)\n---\n'
    elif docformat == 'ConvertOneNoteToMarkDown':
        pattern_meta = r'# (.*)\n\nCreated: (.*)\n\nModified: (.*)\n'
    
    # Variables to store extracted values
    title = None
    updated = None
    created = None
    
    # Function to extract and store values
    def extract_values(match):
        nonlocal title, updated, created
        title = match.group(1)
        updated = match.group(2)
        created = match.group(3)
        return ''  # Return empty string to remove the segment
    
    # Remove the segment from the text and extract values
    cleaned_text = re.sub(pattern_meta, extract_values, text, flags=re.MULTILINE)

    # Only for format onenote-md-exporter, replace the header of title+date+time with just date+time
    if docformat == 'onenote-md-exporter':
        # Regular expression to match date and time
        pattern_header = rf"""
            ^[ \t]*\s*(^{re.escape(title)}$)\s*\n
            (?:[A-Za-z]+\,\s)?([A-Za-z]+\s\d{{1,2}}\,\s\d{{4}})\n
            (\d{{1,2}}:\d{{2}}\s?[APMapm]{{2}})\n
            ([\s\S]*$)"""

        # Search for the pattern in the text
        match = re.search(pattern_header, cleaned_text, re.MULTILINE | re.VERBOSE)
        if match:
            # Format the output as "date, time\n[rest of text]"
            cleaned_text = f"{match.group(2)}, {match.group(3)}\n{match.group(4)}"

            # Ensure an empty document with sub-documents has a new line below date/time
            if match.group(4) == '':
                cleaned_text = cleaned_text + '\n'

    # Only for format onenote-md-exporter, account for a bug where the title+date+time spells just "PM"
    if docformat == 'onenote-md-exporter':
        pattern_broken_header = r"""
        ^\n                   # Start with a newline
        (AM|PM)\s*           # "AM" or "PM" followed by optional whitespace
        \n                    # Another newline
        ([\s\S]*$)           # Capture the rest of the document
    """

        cleaned_text = re.sub(pattern_broken_header, r'\2', cleaned_text, flags=re.VERBOSE)

    # Now add back segment in new format
    metadata_block = f"""- {title}
"""
    if (add_property_metadata == True):
        metadata_block += f"""Created: {created}
 Updated: {updated}
 """
    return cleaned_text, metadata_block, title, created, updated

def is_table_line(line):
    """
    Check if a line is part of a markdown table.
    
    :param line: string of the line to check
    :return: true if the line is part of a table, false otherwise
    """

    return bool(re.match(r"^\s*\|.*\|", line)) or bool(re.match(r"^\s*-{3,}\s*", line))

def is_html_table_open_line(line):
    """
    Check if a line contains the opening of an HTML table
    
    :param line: string of the line to check
    :return: true if there is a <table *> tag
    """

    return bool(re.match(r"<table\b[^>]*>", line, re.IGNORECASE))

def is_html_table_close_line(line):
    """
    Check if a line contains the closing of an HTML table
    
    :param line: string of the line to check
    :return: true if there is a </table *> tag
    """

    return bool(re.match(r"<\/table\b[^>]*>", line, re.IGNORECASE))


def starts_with_html_element(text):
    """
    Regex pattern to match an HTML element at the start of the string,
    possibly preceded by whitespace
    
    :param text: text to check
    :return: true if texte begins with html element, false otherwise
    """

    pattern = r'^\s*<(/?\w+)(?:\s+[^>]*)?/?>'
    
    # Check if the pattern matches at the start of the text
    return bool(re.match(pattern, text, re.DOTALL))

def convert_to_bullets(text):
    """
    Convert a large page of paragraphs into blocks which is more
    appropriate for Logseq.
    
    :param text: text to convert
    :return: same paragraphs as blocks (bullets), with a ' - ' in front of them
    """

    prior_line_was_table = False
    inside_html_table = False

    # Split text into paragraphs
    paragraphs = text.splitlines()

    # Process each paragraph
    bullet_points = []
    for paragraph in paragraphs:
        # Remove leading/trailing whitespace
        #paragraph = paragraph.strip()
        
        # Check if the paragraph already starts with a bullet point
        if re.match(r'^\s*-', paragraph):
            # If it does, add it as is
            bullet_points.append(f"{paragraph}")
        else:
            if is_table_line(paragraph) or starts_with_html_element(paragraph): # table line found

                if prior_line_was_table == False and not inside_html_table: # if this is the first table line, add bullet
                    processed_paragraph = f"- {paragraph}"
                else:
                    processed_paragraph = paragraph

                # Set state of being in or out of a html table
                if is_html_table_open_line(paragraph):
                    inside_html_table = True
                if is_html_table_close_line(paragraph):
                    inside_html_table = False
                
                # Set state of having detected a table line
                prior_line_was_table = True


            else: # not a table line
                prior_line_was_table = False
                if not inside_html_table:
                    processed_paragraph = f"- {paragraph}"
                else:
                    processed_paragraph = paragraph

            bullet_points.append(processed_paragraph)

    # Join the bullet points with newlines to separate paragraphs
    result = '\n'.join(bullet_points)

    return result

def add_space_to_lines(text, number_of_spaces):
    """
    Add a number of tabs in front of a line to indicate the hierarchical level
    This function is used to ensure child pages in OneNote appear as child-blocks
    in Logseq
    
    :param text: source text to process
    :param number_of_spaces: how many levels deep hierarchically to put the text
    :return: same text, but pushed inwards - 2 tabs per level of hierarchy
    """

    # Default value
    if (number_of_spaces == None):
        number_of_spaces = 1

    # Need 2 tabs per level of hierarchy for this to work properly in Logseq
    if (number_of_spaces > 0):
        number_of_spaces *= 2

    # Split the text into lines
    lines = text.splitlines()

    spaced_lines = ''

    # Join the lines back together
    for line in lines:
        spaced_lines += '\t' * number_of_spaces + line + '\n'
    
    return spaced_lines

def process_file(input_file, add_property_metadata, docformat):
    """
    Orchestrate all the processing steps from the source MDs to format suitable
    for Logseq. Basically
        - extract page metadata (title, dates), reformat into Logseq properties
        - rename images to be in Logseq format and their paths to Logseq image folder path
        - apply hierarchical indentation so that child pages become child blocks
        - also produce a set of commands to be executed to modify the image files
    
    :param input_file: path to file to process
    :param add_property_metadata: whether the page metadata (title, dates) should be added as Logseq properties
    :param docformat: whether the MD files were produced using onenote-md-exporter or ConvertOneNoteToMarkDown
    :return: processed text as described above and array of asset (image) names
    """
    
    renimg_commands = ''

    # Read file
    with open(input_file, 'r') as file:
        content = file.read()

    (content, metadata_block, title, created, updated) = process_metadata_segment(content, add_property_metadata, docformat)

    (content, assets) = transform_file_paths(content, updated, docformat)

    content = convert_to_bullets(content)

    # move content inward before adding metadata block under which it will live
    content = add_space_to_lines(content, 1)

    content = metadata_block + content

    # move everything inward based on hierarchy (other files)
    content = add_space_to_lines(content, input_file.count('_'))

    return content, assets

# Main program

# Arguments

# Initialize the argument parser
parser = argparse.ArgumentParser(description="Process input and output folders.")

# Add arguments for input_folder and output_folder
parser.add_argument("--input_folder", type=str, help="Path to the input folder")
parser.add_argument("--output_folder", type=str, help="Path to the output folder")
parser.add_argument("--add_property_metadata", type=str, help="Flag to add property metadata")
parser.add_argument("--format", type=str, help="onenote-md-exporter or ConvertOneNoteToMarkDown")


# Parse the arguments
args = parser.parse_args()

# Assign command line arguments to variables
input_folder = args.input_folder
output_folder = args.output_folder
add_property_metadata = args.add_property_metadata
docformat = args.format


# Default input and output folders

if input_folder == "" or input_folder is None:
    current_folder = os.getcwd()
    input_folder = current_folder

if output_folder == "" or output_folder is None:
    output_folder = input_folder + '/for_logseq/'

output_pages_folder = output_folder + 'pages/'
output_assets_folder = output_folder + 'assets/'

# The output folder may not exist, so create if needed
create_folder_if_not_exists(output_folder)
create_folder_if_not_exists(output_pages_folder)
create_folder_if_not_exists(output_assets_folder)


# Get base folder name from input_folder
base_folder_name = os.path.basename(os.path.normpath(input_folder))

output_file_md = add_trailing_slash(output_pages_folder) + base_folder_name + '.md'


if add_property_metadata != "":
    try:
        add_property_metadata = parse_bool(add_property_metadata)
    except argparse.ArgumentTypeError as e:
        add_property_metadata = False
else:
    # Default metadata value
    add_property_metadata = False

# Counts
cnt_md_processed = 0
cnt_assets_processed = 0
cnt_assets_notfound = 0


# Check if the folder existsto
if not os.path.isdir(input_folder):
    print(f"The input folder {input_folder} does not exist.\n")

else:
    # Get all files in the folder
    md_files = [f for f in os.listdir(input_folder) if os.path.isfile(os.path.join(input_folder, f)) and f.endswith('.md')]

    # Sort the files alphabetically
    md_files.sort()

    # Process each file
    for file_name in md_files:
        file_path = os.path.join(input_folder, file_name)
        #(content, renimg_commands) = process_file(file_path, add_property_metadata)
        (content, assets) = process_file(file_path, add_property_metadata, docformat)

        # Write the result to the output file
        with open(output_file_md, 'a') as f:
            f.write(content + '\n')
            cnt_md_processed += 1

        # Copy renamed image files to new 'assets' folder
        if docformat == 'onenote-md-exporter':
            input_resources_path = os.path.join(input_folder, '../../resources')
        elif docformat == 'ConvertOneNoteToMarkDown':
            input_resources_path = os.path.join(input_folder, '../media')

        for (asset_og, asset_new) in assets:
            src = os.path.join(input_resources_path, asset_og)
            dst = os.path.join(output_assets_folder, asset_new)

            try:
                shutil.copy(src, dst)
                cnt_assets_processed += 1
            except FileNotFoundError:
                print(f"Error: The source file '{src}' was not found.\n")
                cnt_assets_notfound += 1
            except PermissionError:
                print("Error: Permission denied. Check your read/write permissions.\n")
            except IsADirectoryError:
                print("Error: The source or destination is a directory. Use shutil.copytree for directories.\n")
            except OSError as e:
                print(f"Error: An unexpected OS error occurred: {e}\n")

        # Write shell commands to rename the image files
        """with open(output_file_sh, 'a') as f:
            for cmd in renimg_commands:
                f.write(cmd + '\n')
                """

print(f"Processed {cnt_md_processed} MD files and {cnt_assets_processed} images/assets from within them.\n")
if cnt_assets_notfound > 0:
    print(f"Errors: There were {cnt_assets_notfound} assets/images that did not resolve and were note copied.\n")