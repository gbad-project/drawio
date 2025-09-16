from rdflib import Graph, Namespace, URIRef, Literal, BNode
from rdflib.namespace import RDF, RDFS, OWL, DCTERMS
import pandas as pd
from numpy import nan
import re
import urllib.parse
from pprint import pprint
import os
import argparse
import glob
import requests
import uuid

BASE_URI = 'https://data.archives.gov.on.test.gbad.ca/'

from gbad.converter.preprocessors import SourceCSVPreprocessor

# Prohibit trimming pd prints in shell
pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 0)
pd.set_option('display.max_colwidth', None)

# Set labels for reference fields
SISN = 'SISN'
DATEEX_COLS = ['DATEEX_BEGINNING', 'DATEEX_END']
DATEOFF_COLNAME = 'DATEOFF'
DATE_BEGINNING_SUFFIX = '_BEGINNING'
DATE_END_SUFFIX = '_END'
DATECONT_PREFIX = 'DATECONT_'
auth_heading_label = 'HEADING'
add_refd_label = 'REFD'
add_ref_add_label = 'REF_ADD'
add_ref_file_label = 'REF_FILE'
add_title_label = 'TITLE'
mnemonics_contain_title = False # this is used for some checks below
private_mnemonics = ['ARCHAU', 'CMTAU']
auth_authtp_label = 'AUTHTP'
rico_version_mask = r'{RICO_VERSION}'
rico_authtp_mask = r'{RICO_AUTHTP}'
refd_file_mask = r'{REFD_FILE}'
rico_authtp_dict = {
    'CorporateBody': ('Agent', r'/(Corporate Name|[ABC] Ontario Government Name)/'),
    'Family': ('Agent', r'/(Family Name)/'),
    'Place': ('Place', r'/(Geographic Name)/'),
    'Person': ('Agent', r'/(Personal Name)/')
}
uuid_label = 'UUID'
triplesmap_pattern = r'[0-9a-z_-]'
antitriplesmap_pattern = r'[^0-9a-z_-]'

triplesmap_label = 'TriplesMap'
uriref_str_label = 'uriref_str'
map_predicate_label = 'map_predicate'
map_object_label = 'map_object'
increment_number_label = 'increment_number'

# combine_turtle_files generated with Claude 3.5 Sonnet
# on 2024-08-29, with modifications
def add_suppl_triples(source_graph: Graph, root_folder, format="turtle"):
    formats = {
        'turtle': ['ttl', 'turtle'],
        'nt': ['nt'],
        'n3': ['n3'],
        'xml': ['rdf', 'owl', 'xml'],
        'json-ld': ['jsonld', 'json-ld'],
        'nquads': ['nq'],
        'trig': ['trig']
    }

    # Walk through the directory tree
    #for folder_path, _, filenames in os.walk(root_folder): # this is when want to enum all files from subdirs
    def walk_root_folder(folder_path, filenames):
        for filename in filenames:
            # Get the file extension
            file_ext = filename.split('.')[-1]

            # Iterate over formats and check if the extension matches
            for format_name, extensions in formats.items():
                if ((file_ext in extensions) & (format_name == format)):
                    file_path = os.path.join(folder_path, filename)
                    print(f"Adding a supplemental '{format_name}' file: '{file_path}'\n")
                    
                    # Parse the Turtle file and add its contents to the combined graph
                    source_graph.parse(file_path, format=format)

    filenames = (filename for filename in os.listdir(root_folder) if os.path.isfile(os.path.join(root_folder, filename)))
    walk_root_folder(root_folder, filenames)

    return source_graph

def add_preprocess(source_csv_path, preprocessed_csv_path):
    preprocessor = SourceCSVPreprocessor(source_csv_path, preprocessed_csv_path, index_col=SISN)

    def split_by_colon(value: str, expect_num_cols: int):
        SEP = ' : '
        def fix_colon_spacing(value: str) -> str:
            while ': :' in value:
                value = value.replace(': :', ':  :')
            value = value[:-2] if value.endswith(' :') else value  # to fix any ending colon
            value = value[2:] if value.startswith(': ') else value  # to fix any starting colon
            return value
        return preprocessor.separate_value(fix_colon_spacing(value), expect_num_cols, sep=SEP)
    
    def split_by_adjacent_case(value: str, expect_num_cols: int):
        unique_separator = '<split-by-adjacent-case>'
        value = re.sub(r'([^A-Z\s\(\[])([A-Z])', rf'\1{unique_separator}\2', value)
        return preprocessor.separate_value(value, expect_num_cols, sep=unique_separator)
    
    def split_by_hyphen(value: str, expect_num_cols: int):
        if re.fullmatch(r'\d{4}-\d{4}', value) is None:
            value = ''  # won't try to separate these for now
        return preprocessor.separate_value(value, expect_num_cols, sep='-')
    
    # Column split #1
    joint_findaid_col = 'FINDAID:FINDAIDLINK:FINDAID_URL'
    separate_findaid_cols = ['FINDAID', 'FINDAIDLINK', 'FINDAID_URL']
    preprocessor.column_split(split_by_colon, joint_findaid_col, separate_findaid_cols)

    # Column split #2
    joint_iil_col = 'IIL:IIL_URL'
    separate_iil_cols = ['IIL', 'IIL_URL']
    preprocessor.column_split(split_by_colon, joint_iil_col, separate_iil_cols)

    # Column split #3
    indexprov_col = 'INDEXPROV'
    numbered_indexprov_cols = [f"{indexprov_col}_{i}" for i in range(1, 31)]
    preprocessor.column_split(split_by_adjacent_case, indexprov_col, numbered_indexprov_cols)

    # Column split #4
    indexname_col = 'INDEXNAME'
    numbered_indexname_cols = [f"{indexname_col}_{i}" for i in range(1, 31)]
    preprocessor.column_split(split_by_adjacent_case, indexname_col, numbered_indexname_cols)

    # Column split #5
    indexsub_col = 'INDEXSUB'
    numbered_indexsub_cols = [f"{indexsub_col}_{i}" for i in range(1, 31)]
    preprocessor.column_split(split_by_adjacent_case, indexsub_col, numbered_indexsub_cols)

    # Column split #6
    joint_office_col = 'DATEOFF:OFFICEAB:AB_REFA:OFFICEC:C_REFA'
    separate_office_cols = ['DATEOFF', 'OFFICEAB', 'AB_REFA', 'OFFICEC', 'C_REFA']
    numbered_office_cols = []
    for i in range(1, 21):
        numbered_office_cols.extend([f"{col}_{i}" for col in separate_office_cols])
    len(numbered_office_cols)
    preprocessor.column_split(split_by_colon, joint_office_col, numbered_office_cols)

    # Column split #7
    joint_dateoff_colnames = [f'{DATEOFF_COLNAME}_{i}' for i in range(1, 21)]
    for col in joint_dateoff_colnames:
        separate_dateoff_cols = [f"{col}{DATE_BEGINNING_SUFFIX}", f"{col}{DATE_END_SUFFIX}"]
        preprocessor.column_split(split_by_hyphen, col, separate_dateoff_cols)

    # Column logic (not split) #8, co-created with Claude 3.7 Sonnet on 2025-04-21
    for i in range(1, 21):
        # REFA based (main) logic
        ab_refa_colname = f'AB_REFA_{i}'
        c_refa_colname = f'C_REFA_{i}'
        abc_refa_colname = f'ABC_REFA_{i}'
        refa_df = preprocessor.get([ab_refa_colname, c_refa_colname])
        abc_refa_series = refa_df[c_refa_colname].combine_first(refa_df[ab_refa_colname])
        preprocessor.add(abc_refa_colname, abc_refa_series)

        # 1. OFFICE_TYPE: determine by first character
        office_type_colname = f'OFFICE_TYPE_{i}'
        office_type_series = abc_refa_series.str[0].str.upper().map(
            lambda x: x if x in {'A', 'B', 'C'} else None
        )
        preprocessor.add(office_type_colname, office_type_series)

        # 2. OFFICEABC: pick office_ab or office_c based on office type
        officeab_colname = f'OFFICEAB_{i}'
        officec_colname = f'OFFICEC_{i}'
        officeabc_colname = f'OFFICEABC_{i}'
        office_df = preprocessor.get([officeab_colname, officec_colname])
        
        # Initialize the result series with None values (same index as other series)
        officeabc_series = pd.Series(None, index=office_df.index, dtype='object')
        
        # Fill in values based on office type
        # For A or B types, use OFFICEAB
        officeabc_series.loc[office_type_series.isin(['A', 'B'])] = office_df.loc[office_type_series.isin(['A', 'B']), officeab_colname]
        
        # For C type, use OFFICEC
        officeabc_series.loc[office_type_series == 'C'] = office_df.loc[office_type_series == 'C', officec_colname]

        # Add the combined series to the preprocessor
        preprocessor.add(officeabc_colname, officeabc_series)

    preprocessor.dump()

def auth_preprocess(source_csv_path, preprocessed_csv_path, **kwargs):
    preprocessor = SourceCSVPreprocessor(source_csv_path, preprocessed_csv_path, index_col=SISN)
    correct_dateex_path = kwargs.get('correct_dateex_path', None)

    def generate_rico_authtp():
        """Originally generated with Claude Sonnet 4 on 2025-06-25, modified"""
        # Get the authtp columns
        authtp_df = preprocessor.get(['AUTHTP_1', 'AUTHTP_2'])

        added_cols = []
        
        # Process AUTHTP_1 and AUTHTP_2 separately
        for authtp_num in [1, 2]:
            authtp_col = f'AUTHTP_{authtp_num}'
            
            # Initialize result columns for this authtp
            rico_authtp_series = pd.Series(None, index=authtp_df.index, dtype='object')
            rico_authtp_label_series = pd.Series(None, index=authtp_df.index, dtype='object')
            rico_corporatebody_series = pd.Series(None, index=authtp_df.index, dtype='object')
            rico_family_series = pd.Series(None, index=authtp_df.index, dtype='object')
            rico_place_series = pd.Series(None, index=authtp_df.index, dtype='object')
            rico_person_series = pd.Series(None, index=authtp_df.index, dtype='object')
            
            # Process each row for this authtp column
            for idx in authtp_df.index:
                authtp_value = authtp_df.loc[idx, authtp_col]
                
                if pd.notna(authtp_value):
                    # Check against each regex pattern
                    for key, (value, pattern) in rico_authtp_dict.items():
                        pythonic_regex_pattern = pattern[1:-1]
                        if re.search(pythonic_regex_pattern, str(authtp_value)):
                            rico_authtp_series.loc[idx] = value
                            
                            # Set the corresponding specific column
                            if key == 'CorporateBody':
                                rico_corporatebody_series.loc[idx] = value
                                rico_authtp_label_series.loc[idx] = 'Corporate Body'
                            elif key == 'Family':
                                rico_family_series.loc[idx] = value
                                rico_authtp_label_series.loc[idx] = key
                            elif key == 'Place':
                                rico_place_series.loc[idx] = value
                                rico_authtp_label_series.loc[idx] = key
                            elif key == 'Person':
                                rico_person_series.loc[idx] = value
                                rico_authtp_label_series.loc[idx] = key
                            
                            break  # Stop after first match
            
            # Add all the new columns to the preprocessor with appropriate suffix
            rico_authtp_colname = f'RICO_AUTHTP_NEW_{authtp_num}'
            preprocessor.add(rico_authtp_colname, rico_authtp_series)
            added_cols.append(rico_authtp_colname)

            rico_authtp_label_colname = f'RICO_AUTHTP_LABEL_{authtp_num}'
            preprocessor.add(rico_authtp_label_colname, rico_authtp_label_series)
            added_cols.append(rico_authtp_label_colname)

            rico_corporatebody_colname = f'RICO_AUTHTP_CORPORATEBODY_{authtp_num}'
            preprocessor.add(rico_corporatebody_colname, rico_corporatebody_series)
            added_cols.append(rico_corporatebody_colname)

            rico_family_colname = f'RICO_AUTHTP_FAMILY_{authtp_num}'
            preprocessor.add(rico_family_colname, rico_family_series)
            added_cols.append(rico_family_colname)

            rico_place_colname = f'RICO_AUTHTP_PLACE_{authtp_num}'
            preprocessor.add(rico_place_colname, rico_place_series)
            added_cols.append(rico_place_colname)

            rico_person_colname = f'RICO_AUTHTP_PERSON_{authtp_num}'
            preprocessor.add(rico_person_colname, rico_person_series)
            added_cols.append(rico_person_colname)

        print(f"Source preprocessed by adding columns: {added_cols} \n")

    # Add columns necessary for RICO_AUTHTP logic
    generate_rico_authtp()

    def pull_correct_dateex():
        nonlocal correct_dateex_path
        correct_dateex_name = os.path.basename(correct_dateex_path)
        if correct_dateex_path is None:
            return
        try:
            correct_dateex_df = pd.read_csv(correct_dateex_path, index_col=SISN, dtype='object')
            preprocessor.update(correct_dateex_df[DATEEX_COLS])
            
            print(f"Source preprocessed by updating {DATEEX_COLS} with values from '{correct_dateex_name}'\n")
        except Exception as e:
            print(f"Failed to update Authority DATEEX with correct values: '{e}'")
    
    # Update DATEEX with correct values
    pull_correct_dateex()

    preprocessor.dump()

def generic_preprocess(source_csv_path, preprocessed_csv_path, **kwargs):
    preprocessor = SourceCSVPreprocessor(source_csv_path, preprocessed_csv_path)
    preprocessor.dump()

def __init__(schema_code, source_filename=None):
    # Define GBAD schema ontology
    base_data_uri = BASE_URI[:-1]
    #base_gbad_uri = URIRef(f"{base_data_uri}/RiC-O_1-0-1")
    base_gbad_uri = base_data_uri
    base_schema_uri = URIRef(f"{base_data_uri}/Schema")
    #base_kb_uri = URIRef(f"{base_data_uri}/KB")
    base_auth_uri = URIRef(f"{base_schema_uri}/Authority")
    base_add_uri = URIRef(f"{base_schema_uri}/Description-Listings")
    base_mapping_uri = URIRef(f"{base_schema_uri}/Mapping")
    # Not using these two below anymore because UUIDs are now from URL namespace
    #MAPPING_NS_UUID = uuid.uuid5(uuid.NAMESPACE_URL, f"{base_mapping_uri}#")
    #print(f"Namespace UUID v5 for <{base_mapping_uri}#>: {MAPPING_NS_UUID}\n")

    base_uri_prefix = f"{base_data_uri}/"
    schema_term = 'Schema'
    auth_term = 'Authority'
    add_term = 'Description-Listings'
    maps_term = 'Mapping'
    kb_term = 'KB'

    def get_second_term():
        if schema_code == 'auth':
            return auth_term
        elif schema_code == 'add':
            return add_term
        else:
            raise Exception(f"Fatal error: Schema code not supplied or supported.")

    # Any supported schema namespaces
    schema_regex_str = rf'^({auth_term}|{add_term}|{maps_term})/([A-Za-z_]+)(#.*|/.*)?$'
    schema_regex = re.compile(schema_regex_str, flags=re.IGNORECASE)

    # Any mnemonic-based URIs in GBAD URI syntax
    mnemonic_pattern = r"\{([A-Z:_\d\.]+)\}"
    mnemonic_regex = re.compile(rf"([a-zA-Z]+)/({mnemonic_pattern})/?(.*)")
    # Camel case separation
    camelcase_pattern = r"(?<=[a-z])(?=[A-Z])"
    camelcase_regex = re.compile(camelcase_pattern)
    def decamelize(s): s = camelcase_regex.sub(' ', s); return s[0].upper() + s[1:] # uppercase custom properties
    # Pattern to capture within-mnemonic iterators
    mnemonic_i_pattern = r"(\d+)\.\.(\d+)"
    mnemonic_i_regex = re.compile(mnemonic_i_pattern)

    def get_mnemonic_i_from_to(mnemonic):
        mnemonic_i_from, mnemonic_i_to = 1, 1
        if mnemonic:
            mnemonic_i_matches = mnemonic_i_regex.findall(mnemonic)
            mnemonic_i_match_count = len(mnemonic_i_matches)
            if mnemonic_i_match_count == 0:
                pass
            elif mnemonic_i_match_count > 1:
                raise Exception(f"Error while handling '{mnemonic}' mnemonic: ",
                                f"{mnemonic_i_match_count} increment requests detected while max one allowed.")
            else:
                mnemonic_i_from, mnemonic_i_to = int(mnemonic_i_matches[0][0]), int(mnemonic_i_matches[0][1])
        return mnemonic_i_from, mnemonic_i_to

    # This intends to support any RiC-O versions, past and future
    semver_pattern = r'(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?'
    def gbadify_rico_version(semver_str): return 'RiC-O_' + semver_str.replace('.', '-')
    # The commented below are useful to recognize any RiC-O version mask in GBAD URIs
    def gbadify_rico_pattern(semver_pattern): return 'RiC-O_' + semver_pattern.replace(r'\.', '-')
    gbad_term_pattern = gbadify_rico_pattern(semver_pattern)
    gbad_term_regex = re.compile(rf"^({gbad_term_pattern})/.+", re.IGNORECASE)

    # Logic for getting the current version
    rico_uri = 'https://www.ica.org/standards/RiC/ontology#'
    def get_rico_version():
        # Try to request the OWL file using content negotiation
        headers = {'Accept': 'application/xml'}
        response = requests.get(rico_uri, headers=headers)
        # Check if we received RDF/XML content
        try:
            rico_graph = Graph()
            rico_graph.parse(data=response.text, format="xml")
            query = f"""
            SELECT ?versionIRI WHERE {{
                ?s <{OWL.versionIRI}> ?versionIRI .
            }}
            """
            for row in rico_graph.query(query):
                pattern = re.compile(rf'\/({semver_pattern})$')
                match = pattern.search(row.versionIRI)
                return match.group(1)
        except:
            pass

        return None
    
    ### Start block for downloading RiC-O version
    #try:
    #    gbad_term = gbadify_rico_version(get_rico_version())
    #except:
    #    exit(f"Exiting. Fatal error: Could not resolve RiC-O version from '{rico_uri}'")
    #def substitute_rico_version_mask(s): return str(s).replace(rico_version_mask, gbad_term) if str(s).startswith(rico_version_mask) else str(s)
    ### End block for downloading RiC-O version

    # The below works but commented out for now because did not do the trick without accessing input CSV values
    # That is, the UUID is only unique to the TriplesMap, so all entities generated from it have the same UUID
    # Define UUID replacement logic - support any prefix or suffix (to diversify UUIDs) but only allowed chars
    uuid_pattern = f"{{({uuid_label}({triplesmap_pattern}*)|({triplesmap_pattern}*){uuid_label})}}" # unencoded curly brackets because regex applied before encoding
    uuid_regex = re.compile(uuid_pattern, flags=re.IGNORECASE) # let's make it case-insensitive to allow flexibility for different URI formats

    def concat_full_mapping_entity_uri(entity_name):
        return URIRef(f"{base_mapping_uri}#{entity_name}")

    def generate_uuid_str(entity_name, show_message=True):
        full_uri = concat_full_mapping_entity_uri(entity_name)
        uuid_str = str(uuid.uuid5(uuid.NAMESPACE_URL, full_uri))
        if show_message:
            print(f"UUID v5 generated from ns:URL and <{full_uri}>: {uuid_str}\n")
        return uuid_str

    def substitute_uuid(uriref, uuid_str):
        uriref = uuid_regex.sub(uuid_str, uriref)
        return URIRef(uriref) if isinstance(uriref, URIRef) else Literal(uriref)

    def prettify_rdfs_label(literal_str):
        #return literal_str # no massive prettification anymore as of 2025-02-14 edition
        # because draw io parser is now run with --label-disable, and thus
        # rdfs:label template must be specified in drawio file or none is generated

        # Make sure no encoded chars remain, in particular those can come from rr:constant
        literal_str = urllib.parse.unquote(literal_str)

        # Remove base data prefix
        if literal_str.startswith(base_uri_prefix):
            literal_str = str(literal_str[len(base_uri_prefix):])

        # Remove any relative URI indicator
        if literal_str.startswith('/') or literal_str.startswith('#'):
            literal_str = str(literal_str[1:])

        # Schema entities
        if literal_str.lower().startswith(schema_term.lower() + '/'):
            literal_str = str(literal_str[len(schema_term)+1:])
            match = schema_regex.search(literal_str)
            if match:
                literal_str = match.group(0)
                #auth_add_maps_term = match.group(1)
                rico_class_ish_term = decamelize(match.group(2))
                last_term =  match.group(3)
                if last_term is None:
                    literal_str = rico_class_ish_term
                elif str(last_term).startswith('#'):
                    literal_str = f"{rico_class_ish_term}: {last_term[1:]}"
                elif str(last_term).startswith('/'):
                    literal_str = last_term[1:]
                else:
                    pass
                #literal_str = str(literal_str[len(auth_add_maps_term)+1:])
                #literal_str = literal_str + f' ({auth_add_maps_term} Schema Entity)'

        # KB entities
        if literal_str.lower().startswith(kb_term.lower() + '/'):
            literal_str = str(literal_str[len(kb_term)+1:])
            #literal_str = literal_str + ' (Knowledge Base Entity'
            match = re.search(mnemonic_regex, literal_str)
            if match:
                #print(match.groups()) # keeping this because I forget how to show all groups
                rico_ish_class = decamelize(match.group(1))
                mnemonic_mask = match.group(2)
                mnemonic = match.group(3)
                optional_rest = match.group(4)
                # Hardcode a few cases for readability.
                # If {TITLE} is not set for these, they'll be dropped by RML Mapper.
                # I cannot check the value, which is bad. So they'll probably be dropped. Wicked warning added below.
                # At least, here is a patch that {TITLE} is at least requested by user,
                # or else it would be strange to receive this error:
                #if mnemonics_contain_title: # this will have been checked by the time this is invoked
                    # So if {TITLE} is at least present, RML Mapper won't give an error
                    # Case 1. Assumed to have full ref code
                #    if mnemonic in [add_refd_label,add_ref_file_label]:
                #        mnemonic_mask = f'{{TITLE}}. {{{mnemonic}}}'
                #        print(f"Invoking rdfs:label replacement for '{literal_str}'. The following mask will be used: '{mnemonic_mask}'. Note that whenever any of the referenced columns is empty, these rdfs:label triples may be dropped by RML Mapper. To work around, ensure that all such records contain a value in all of the referenced columns.")
                    # Case 2. Will only happen if no REF_FILE per disaggregate_refd_file logic,
                    # or if the same is set manually in drawio
                #    elif mnemonic == add_ref_add_label and optional_rest.startswith('{TITLE}'): 
                #        mnemonic_mask = f'{{TITLE}}. {{{mnemonic}}}-?' # hardcode for readability
                literal_str = f'{mnemonic_mask} ({rico_ish_class})'
                if optional_rest: # anything, importantly UUID
                    literal_str = f'{mnemonic_mask} ({rico_ish_class} - {optional_rest})'
                #literal_str = literal_str + f' from "{mnemonic}"'
            #literal_str = literal_str + ')'

        # GBAD entities - deprecated as of 2024-11-14 :(
        #gbad_term_match = gbad_term_regex.match(literal_str)
        #if gbad_term_match:
        #    matched_gbad_term = gbad_term_match.group(1)
        #    literal_str = str(literal_str[len(matched_gbad_term)+1:])
        #    match = mnemonic_regex.match(literal_str)
        #    if match:
        #        mnemonic_group = match.group(1) # in curly brackets
        #        mnemonic  = match.group(2)
        #        rico_class = match.group(3)
        #        instance_number = match.group(4)
                #literal_str = f'{mnemonic_group} ({rico_class} Entity'
                #if instance_number:
                #    instance_number = instance_number[1:] # leading slash removed
                #    literal_str = literal_str + f' #{instance_number}'
                #literal_str = literal_str + f' from "{mnemonic}")'
        #        literal_str = f'{{{mnemonic}}} ({rico_class})'
        
        return literal_str

    # Choose ontology to map
    base_uri = base_data_uri
    #suppl_graph_dir = 'gbad/schema' # to add any standalone ttls in schema dir

    # Set schema-specific params
    if schema_code == 'add':
        # Assume the first file found
        graph_dir = 'gbad/schema/description-listings'
        graph_path = glob.glob(os.path.join(graph_dir, "*.ttl"))[0]
        
        # ADD: Choose source CSV for mapping
        if source_filename is None:
            source_filename = 'description_tailshuf_100.csv'
    
    elif schema_code == 'auth':
        #suppl_graph_dir = 'gbad/schema/authority_AgentControlRelation'
        # Assume the first file found
        graph_dir = 'gbad/schema/authority/'
        graph_path = glob.glob(os.path.join(graph_dir, "*.ttl"))[0]

        # Authority: Choose source CSV for mapping
        if source_filename is None:
            source_filename = 'authority_tailshuf_100.csv'

        # Additional sources
        correct_dateex_path = 'gbad/mapping/source/New-export-of-Government-authorities-with-correct-Dates-of-Existence-xlsx.csv'

    elif schema_code == 'generic':
        graph_dir = 'gbad/schema/generic'
        # Assume the first file found
        graph_path = glob.glob(os.path.join(graph_dir, "*.ttl"))[0]

        # ADD: Choose source CSV for mapping
        if source_filename is None:
            source_filename = 'generic.csv'

    else:
        raise Exception(f"Fatal error: Schema code not supplied.")

    if source_filename:
        source_path = f'gbad/mapping/source/{source_filename}'
        print(f"Using source file: '{source_path}'\n")
        print(f"Checking in for preprocessing...\n")
        if schema_code == 'add':
            preprocessed_csv_path = f'gbad/mapping/source/preprocessed/{source_filename}'
            add_preprocess(source_path, preprocessed_csv_path)
            source_path = preprocessed_csv_path
        elif schema_code == 'auth':
            preprocessed_csv_path = f'gbad/mapping/source/preprocessed/{source_filename}'
            auth_preprocess(source_path,
                            preprocessed_csv_path,
                            correct_dateex_path=correct_dateex_path)
            source_path = preprocessed_csv_path
        elif schema_code == 'generic':
            preprocessed_csv_path = f'gbad/mapping/source/preprocessed/{source_filename}'
            generic_preprocess(source_path, preprocessed_csv_path)
            source_path = preprocessed_csv_path
        else:
            print("No preprocessing scheduled - none attempted.")
    print(f"Using source file: '{source_path}'\n")

    rml_path = graph_path[:-3]+ "rml"
    if source_filename:  # Override default
        graph_name = os.path.splitext(os.path.basename(graph_path))[0]
        rml_path = f'{graph_dir}/{os.path.splitext(source_filename)[0]}/{graph_name}'+ ".rml"

    # Create the input RDF graph
    g = Graph(base = base_uri)
    print(f"Using graph: '{graph_path}'\n")
    g.parse(graph_path,
            format="turtle")  # Adjust the format as needed

    # Add additional triples
    #if suppl_graph_dir:
    #    g = add_suppl_triples(g, suppl_graph_dir, format="turtle")

    # Define custom prefixes
    rico = ('rico', Namespace(rico_uri))
    ns = ('data', Namespace(URIRef(f"{base_uri}/")))
    auth = ('auth', Namespace(URIRef(f"{base_auth_uri}/")))
    add = ('add', Namespace(URIRef(f"{base_add_uri}/")))
    maps = ('maps', Namespace(URIRef(f"{base_mapping_uri}#")))

    # Prefix for prefix set when running drawio parser
    DRAWIO_PREFIX = f"{maps[0]}:"  # used later in trimming

    # Define common prefixes
    rdf = ('rdf', RDF)
    rdfs = ('rdfs', RDFS)
    owl = ('owl', OWL)

    # Define RML-specific prefixes
    rml = ('rml', Namespace('http://semweb.mmlab.be/ns/rml#'))
    rr = ('rr', Namespace('http://www.w3.org/ns/r2rml#'))
    ql = ('ql', Namespace('http://semweb.mmlab.be/ns/ql#'))
    csvw = ('csvw', Namespace('http://www.w3.org/ns/csvw#'))

    # Namespaces for FnO to work at RML mapping
    fnml = ('fnml', Namespace('http://semweb.mmlab.be/ns/fnml#'))
    fno = ('fno', Namespace('https://w3id.org/function/ontology#'))
    idlab_fn = ('idlab-fn', Namespace('https://w3id.org/imec/idlab/function#'))
    grel = ('grel', Namespace('http://users.ugent.be/~bjdmeest/function/grel.ttl#'))

    # Bind prefixes to namespaces
    g.namespace_manager.bind(*rico)
    g.namespace_manager.bind(*rdf)
    g.namespace_manager.bind(*rdfs)
    g.namespace_manager.bind(*owl)
    g.namespace_manager.bind(*ns)
    g.namespace_manager.bind(*auth)
    g.namespace_manager.bind(*add)
    g.namespace_manager.bind(*maps)
    g.namespace_manager.bind(*rml)
    g.namespace_manager.bind(*rr)
    g.namespace_manager.bind(*ql)
    g.namespace_manager.bind(*csvw)
    g.namespace_manager.bind(*fnml)
    g.namespace_manager.bind(*fno)
    g.namespace_manager.bind(*idlab_fn)
    g.namespace_manager.bind(*grel)

    #print(g.serialize(format='turtle'))

    # Query to get all subjects, predicates, and objects
    query = f"""
    SELECT ?subject ?predicate ?object
    WHERE {{
    ?subject ?predicate ?object.
    }}
    """
    # Execute the query
    result = g.query(query)

    # List to hold the parsed results
    parsed_results = []

    rico_authtp_subjects = dict() # keeping these out for future use
    def disaggregate_rico_authtp(spo):
        if schema_code == 'generic':
            return [spo]
        subject_uri, predicate_uri, object_uri = spo
        rico_disaggregated_subjects = []
        rico_disaggregated_objects = []
        rico_disaggregated_triples = []

        # Necessary to make matches and replacements work
        rico_authtp_mask_encoded = urllib.parse.quote(rico_authtp_mask, safe='')
        subject_mask = rico_authtp_mask_encoded if isinstance(subject_uri, URIRef) else rico_authtp_mask
        object_mask = rico_authtp_mask_encoded if isinstance(object_uri, URIRef) else rico_authtp_mask

        # Replacing subject
        if subject_mask in str(subject_uri):
            for authtp_rico_class, rico_authtp_tuple in rico_authtp_dict.items():
                rico_authtp_uri_term, authtp_value = rico_authtp_tuple
                # If contains {RICO_AUTHTP}
                # Add two subjects for easy separate triplesmap creation later on
                for authtp_i in [1, 2]:
                    authtp_column_name = f"{auth_authtp_label}_{authtp_i}"
                    replacement = f"{authtp_rico_class}_{authtp_column_name}" # class is used for uniqueness
                    rico_disaggregated_subject_uri = str(subject_uri).replace(subject_mask, replacement)

                    if isinstance(subject_uri, URIRef):
                        rico_disaggregated_subject_uri = URIRef(rico_disaggregated_subject_uri)
                    else:
                        rico_disaggregated_subject_uri = Literal(rico_disaggregated_subject_uri)
                    rico_disaggregated_subjects.append(rico_disaggregated_subject_uri)
                    # Keep an external list of these for future use
                    if not rico_disaggregated_subject_uri in rico_authtp_subjects.keys():
                        true_rico_disaggregated_subject_uri = str(subject_uri).replace(subject_mask, rico_authtp_uri_term) # actual term
                        if isinstance(subject_uri, URIRef):
                            true_rico_disaggregated_subject_uri = URIRef(true_rico_disaggregated_subject_uri)
                        else:
                            true_rico_disaggregated_subject_uri = Literal(true_rico_disaggregated_subject_uri)
                        rico_authtp_subjects[rico_disaggregated_subject_uri] = (true_rico_disaggregated_subject_uri, authtp_column_name)

                    # If is a triple like ?s a rico:Thing
                    if ((predicate_uri == rdf[1].type) and
                        (object_uri == rico[1].Thing)):
                        rico_disaggregated_object_uri = URIRef(str(object_uri).replace('Thing',
                                                                                        authtp_rico_class))
                        rico_disaggregated_triples.append((rico_disaggregated_subject_uri,
                                                        predicate_uri,
                                                        rico_disaggregated_object_uri))
        else:
            rico_disaggregated_subjects.append(subject_uri)

        if len(rico_disaggregated_triples) == 0: # if not a triple like ?s a rico:Thing
            # Replacing object
            if object_mask in str(object_uri):
                for authtp_rico_class, rico_authtp_tuple in rico_authtp_dict.items():
                    rico_authtp_uri_term, authtp_value = rico_authtp_tuple
                    # If contains {RICO_AUTHTP}
                    # Add two subjects for easy separate triplesmap creation later on
                    for authtp_i in [1, 2]:
                        authtp_column_name = f"{auth_authtp_label}_{authtp_i}"
                        replacement = f"{authtp_rico_class}_{authtp_column_name}" # class is used for uniqueness
                        rico_disaggregated_object_uri = str(object_uri).replace(object_mask, replacement)

                        if isinstance(object_uri, URIRef):
                            rico_disaggregated_object_uri = URIRef(rico_disaggregated_object_uri)
                        else:
                            rico_disaggregated_object_uri = Literal(rico_disaggregated_object_uri)
                        rico_disaggregated_objects.append(rico_disaggregated_object_uri)
            elif len(rico_disaggregated_objects) == 0: 
                rico_disaggregated_objects.append(object_uri)
            
            # Collect all subjects and objects
            for rico_disaggregated_subject in rico_disaggregated_subjects:
                for rico_disaggregated_object in rico_disaggregated_objects:
                    rico_disaggregated_triples.append((rico_disaggregated_subject,
                                                    predicate_uri,
                                                    rico_disaggregated_object))

        return rico_disaggregated_triples
    
    def disaggregate_refd_file(spo):
        subject_uri, predicate_uri, object_uri = spo
        ref_disaggregated_subjects = []
        ref_disaggregated_objects = []
        ref_disaggregated_triples = []

        # Substitute correct terms
        ref_terms = []
        if schema_code == 'auth' or schema_code == 'generic': # no need to execute
            return [spo]
        elif schema_code == 'add': # add all options - empty fields will be skipped by RML mapper
            ref_terms.extend([
                f'{{{add_refd_label}}}',
                f'{{{add_ref_file_label}}}' # decided on 2025-02-14 that REF_FILE must be present
                # at all times and must contain REF_ADD already, and those records that don't have that
                # must be isolated and dealt with separately
                #f'{{{add_ref_add_label}}}/{{{add_title_label}}}'
            ])
        else:
            raise Exception(f"Fatal error: Schema code not supplied or supported.")

        # Necessary to make matches and replacements work
        refd_file_mask_encoded = urllib.parse.quote(refd_file_mask, safe='')
        subject_mask = refd_file_mask_encoded if isinstance(subject_uri, URIRef) else refd_file_mask
        object_mask = refd_file_mask_encoded if isinstance(object_uri, URIRef) else refd_file_mask

        # Replacing subject
        if subject_mask in str(subject_uri): # If contains {REFD_FILE}
            for ref_term in ref_terms: # One with REFD, one with REF_FILE, and one with TITLE
                ref_term_encoded = urllib.parse.quote(ref_term, safe='')
                if isinstance(subject_uri, URIRef):
                    ref_disaggregated_subject_uri = str(subject_uri).replace(subject_mask, ref_term_encoded)
                    ref_disaggregated_subject_uri = URIRef(ref_disaggregated_subject_uri)
                else:
                    ref_disaggregated_subject_uri = str(subject_uri).replace(subject_mask, ref_term)
                    ref_disaggregated_subject_uri = Literal(ref_disaggregated_subject_uri)
                ref_disaggregated_subjects.append(ref_disaggregated_subject_uri)
        else:
            ref_disaggregated_subjects.append(subject_uri)

        # Replacing object
        if object_mask in str(object_uri): # If contains {REFD_FILE}
            for ref_term in ref_terms: # One with REFD, one with REF_FILE, and one with TITLE
                ref_term_encoded = urllib.parse.quote(ref_term, safe='')
                if isinstance(object_uri, URIRef):
                    ref_disaggregated_object_uri = str(object_uri).replace(object_mask, ref_term_encoded)
                    ref_disaggregated_object_uri = URIRef(ref_disaggregated_object_uri)
                else:
                    ref_disaggregated_object_uri = str(object_uri).replace(object_mask, ref_term)
                    ref_disaggregated_object_uri = Literal(ref_disaggregated_object_uri)
                ref_disaggregated_objects.append(ref_disaggregated_object_uri)
        else: 
            ref_disaggregated_objects.append(object_uri)
        
        # Collect all subjects and objects
        for ref_disaggregated_subject in ref_disaggregated_subjects:
            for ref_disaggregated_object in ref_disaggregated_objects:
                ref_disaggregated_triples.append((ref_disaggregated_subject,
                                                predicate_uri,
                                                ref_disaggregated_object))

        return ref_disaggregated_triples

    # Process the results and create new triples
    for row in result:
        subject = row.subject
        predicate = row.predicate
        object = row.object

        ref_disaggregated_triples = disaggregate_refd_file((subject, predicate, object))
        for ref_disaggregated_triple in ref_disaggregated_triples:
            rico_disaggregated_triples = disaggregate_rico_authtp(ref_disaggregated_triple)
            for s, p, o in rico_disaggregated_triples:
                parsed_results.append({
                    'subject': s,
                    'predicate': p,
                    'object': o
                })
        
    #print(parsed_results[:5]) # debug

    # Convert the parsed results to a dataframe
    parsed_df = pd.DataFrame(parsed_results)
    # Dropping duplicates is necessary due to the duplicated classes
    # in rico_authtp_dict as this duplicates #rr_template__KB_CorporateBody__HEADING__
    # thus producing an error at RML mapping
    #parsed_df = parsed_df.drop_duplicates()
    #parsed_df.to_csv('parsed_df.csv') # for debug

    def normalize_uri(uri, ns_manager):
        if isinstance(uri, URIRef):
            return ns_manager.normalizeUri(uri)
        return None

    # SELECT ?s a ?o
    allowed_non_rico_classes = [
        owl[1].DatatypeProperty
    ]
    subjects_df = parsed_df[
        (parsed_df['predicate'].apply(lambda x: str(normalize_uri(x, g.namespace_manager))) == 'rdf:type') &
        (parsed_df['object'].apply(lambda x:
                                   (str(normalize_uri(x, g.namespace_manager)).startswith(f"{rico[0]}:") or
                                    x in allowed_non_rico_classes)))
    ].loc[:,['subject','object']] # So to be sure, object is the rdf:type URI here

    def extract_uriref_str(uriref):
        norm_uri = normalize_uri(uriref, g.namespace_manager)
        if not norm_uri:
            #map_series = uriref_str_to_map(uriref)
            #if map_series[map_predicate_label]:
                # This is a tricky part but really important because
                # otherwise nodes that are drawn as non-class nodes
                # are simply dropped. So this part tries to process
                # the "uriref" (which is really a literal in this case)
                # to produce a map, and if successful, that means that
                # input uriref is already uriref_str, so we are returning it.
            # Sorry, this is even simpler! Any input uriref which is not norm_uri
            # actually has to be returned as uriref because it means that it is
            # has to be passed on as a literal. By contrast, if only the if block
            # above is implemented, non-map series structures literals are dropped.
            # Thus, we are simply returning any literal as uriref.
            return uriref
            #return None
        # Replace namespace URIs with prefix codes
        uriref_str = str(norm_uri)
        # Remove base URI prefix
        uriref_str = uriref_str.replace(DRAWIO_PREFIX, '')
        # Decode special URI entities
        uriref_str = urllib.parse.unquote(uriref_str)
        return uriref_str
    
    def triplesmap_clean(str):
        # Replace with underscores anything but Latin letters, numbers, hyphens, and underscores
        triplesmap_name = re.sub(antitriplesmap_pattern, '_', str, flags=re.IGNORECASE)
        return triplesmap_name

    def generate_triplesmap_name(row, show_message=False):
        def series(triplesmap_name, uuid_str):
            map_series = pd.Series({
                triplesmap_label: triplesmap_name,
                uuid_label: uuid_str
            })
            return map_series
        
        # This implementation assumes that subject URIs are unique
        subject_uri = row.get('subject', None)
        if not pd.isna(subject_uri):
            subject_str = extract_uriref_str(subject_uri)
            cleaned_subject = triplesmap_clean(subject_str)
            # Not showing message because we would only need to see it for rows with {UUID},
            # and this is implemented in UUID substitution logic
            uuid_str = generate_uuid_str(cleaned_subject, show_message=show_message)
            return series(cleaned_subject, uuid_str)
        return series(None, None)
    
    # Necessary to init namespace manager for uriref_str_to_map
    # Initialize an RDF graph
    mapping = Graph(base = URIRef(f"{base_gbad_uri}/"))
    
    def uriref_str_to_map(uriref_str, uuid_str=None):
        map_predicate = None
        map_object = None

        def series(map_predicate, map_object):
            map_series = pd.Series({
                map_predicate_label: map_predicate,
                map_object_label: map_object
            })
            return map_series

        if not uriref_str:
            return series(map_predicate, map_object)
        
        uriref_str = re.sub(r'\s+', ' ', uriref_str)

        def remove(predicate: URIRef, uriref_str):
            sin_predicate = re.sub(rf"^{str(predicate)}\s+", "", uriref_str)
            sin_predicate = sin_predicate.strip('"')
            return sin_predicate
        
        def norm(uriref):
            return str(normalize_uri(uriref, g.namespace_manager))
        
        # Literal mapped from source
        if uriref_str.startswith(norm(rml[1].reference)):
            map_predicate = rml[1].reference
            map_object = Literal(remove(norm(map_predicate), uriref_str))
        # URI mapped from source
        elif uriref_str.startswith(norm(rr[1].template)):
            map_predicate = rr[1].template
            cleaned_uri = remove(norm(map_predicate), uriref_str)
            # This is where the actual UUID substitution happens when UUID accompanies mnemonics
            if uuid_str:
                cleaned_uri = substitute_uuid(cleaned_uri, uuid_str)
            encoded_uri = URIRef(urllib.parse.quote(cleaned_uri, safe=''))
            if isinstance(cleaned_uri, URIRef): # check if true URI or rr:template
                map_object = URIRef(encoded_uri)
            else:
                #cleaned_uri = substitute_rico_version_mask(cleaned_uri)
                map_object = Literal(cleaned_uri)
        # Constant URI
        elif uriref_str.startswith(norm(rr[1].constant)):
            map_predicate = rr[1].constant
            cleaned_uri = remove(norm(map_predicate), uriref_str)
            if cleaned_uri.startswith('/') or cleaned_uri.startswith('#') :
                cleaned_uri = base_data_uri + cleaned_uri
            # This is where the actual UUID substitution happens when UUID is the only mask
            if uuid_str:
                cleaned_uri = substitute_uuid(cleaned_uri, uuid_str)
            encoded_uri = URIRef(urllib.parse.quote(cleaned_uri, safe=":/#?&="))
            if isinstance(encoded_uri, URIRef): # check if true URI or constant literal
                map_object = URIRef(encoded_uri)
            else:
                map_object = Literal(cleaned_uri)
        # Treat anything else as a literal
        else:
            map_object = Literal(uriref_str)

        return series(map_predicate, map_object)
    
    def review_mnemonics(matches):
        global mnemonics_contain_title
        if add_title_label in matches:
            mnemonics_contain_title = True
    
    def extract_mnemonic(row, all=False):
        map_predicate = row[map_predicate_label]
        map_object = row[map_object_label]
        uuid_str = row.get(uuid_label, None)
        if map_object:
            if map_predicate == rml[1].reference:
                return map_object
            elif map_predicate != rr[1].template:
                return None
            # Consider replacing this with more robust, findall logic
            # later on to allow for true multiple masks
            #map_object = substitute_rico_version_mask(map_object)
            if uuid_str:
                map_object = substitute_uuid(map_object, uuid_str)
            matches = re.findall(mnemonic_pattern, map_object)
            if matches:
                review_mnemonics(matches) # neat spot to check each mnemonic ever one by one
                if len(matches) > 1:
                    # If there is a predicate column set in row, then we are iterating over parsed_df objects,
                    # which means we already saw the warning when iterating over disaggregated subjects_df
                    # Then if there is no triplesmap name set, then this is subjects_df before disaggregation,
                    # and we do not want to see the warning yet because URIs are not yet final
                    #show_warning = (row.get('predicate', None) is None and
                    #                row.get(triplesmap_label, None) is not None)
                    # Means we're at disaggregated objects already:
                    show_warning = (row.get('original_object', None) is not None)
                    if show_warning:
                        #print(set(matches)==set(['REF_ADD','TITLE'])) - this works btw; just in case want to put some logic here
                        other_mnemonics = ", ".join([f"{{{match}}}" for match in matches[1:]])
                        if uuid_str:
                            generate_triplesmap_name(row, show_message=True)  # just to show the message
                        if all is not True:
                            print("At most one rr:template is allowed per subject map ",
                                f"whereas multiple are given in: '{map_object}'. ",
                                f"By default logic, the leftmost mnemonic is deliberately chosen as the main one.",
                                f"Thus, {{{matches[0]}}} will be processed as the main mnemonic, "
                                f"and all the others will be passed to RML as is: {other_mnemonics}", "\n")
                    #return None
                return matches if all is True else matches[0]
        return None
    
    def generate_rico_name(row):
        object_uri = row['object']
        object_str = str(normalize_uri(object_uri, g.namespace_manager))
        cleaned_object = object_str
        return cleaned_object
    
    rico_name_label = 'RiC-O Name'.replace(' ','_')
    mnemonic_label = 'Authority Mnemonic'.replace(' ','_')

    def collect_incremented_uri(row, column, disaggregated_series_list):
        #row_id = row.name
        row[f'original_{column}'] = row[column]

        # If increment number in row, then disaggregation already done (e.g., for subject)...
        increment_number = row.get(increment_number_label, None)

        # Extract all mnemonics
        mnemonics = extract_mnemonic(row, all=True)

        # If not map_object, return unchanged
        if mnemonics is None:
            new_row = row.copy()  # because row is passed by reference, data are lost unless this is copied!
            disaggregated_series_list.append(new_row)
            return row

        # Analyze i data for all mnemonics
        mnemonic_dict = {}
        mnemonic_to_max = 1
        for mnemonic in mnemonics:
            # Uncomment the below if want to allow increments outside of mnemonics
            #mnemonic_i_from, mnemonic_i_to = get_mnemonic_i_from_to(column_uri)
            mnemonic_i_from, mnemonic_i_to = get_mnemonic_i_from_to(mnemonic)
            if isinstance(increment_number, int): # ...so will only generate one row with the inherited increment number (e.g., for object)
                mnemonic_i_from = increment_number; mnemonic_i_to = increment_number
            if mnemonic_i_to > mnemonic_to_max:
                mnemonic_to_max = mnemonic_i_to
            mnemonic_dict[mnemonic] = (mnemonic_i_from, mnemonic_i_to)

        # Iterate over and replace all mnemonics
        new_rows = [None] * (mnemonic_to_max + 1)  # because counting mnemonics from 1
        for mnemonic, mnemonic_i_tuple in mnemonic_dict.items():
            mnemonic_i_from, mnemonic_i_to = mnemonic_i_tuple

            for mnemonic_i in range(mnemonic_i_from, mnemonic_i_to + 1):
                if new_rows[mnemonic_i] is None:  # then this mnemonic_i is not yet in new_rows
                    new_rows[mnemonic_i] = row.copy()
                column_uri = new_rows[mnemonic_i][column]
                if not (mnemonic_i_from == 1 and mnemonic_i_to == 1): # doesn't make sense to add this then
                    new_rows[mnemonic_i][increment_number_label] = mnemonic_i
                column_value = mnemonic_i_regex.sub(str(mnemonic_i), str(column_uri))
                if column_value:
                    new_rows[mnemonic_i][column] = URIRef(column_value) if isinstance(column_uri, URIRef) else Literal(column_value)

        dense_new_rows = [row for row in new_rows if row is not None]  # drop any None's
        disaggregated_series_list.extend(dense_new_rows)

        return row
    
    # Note for next line that it is the only one that applies to series, all other to df
    subjects_df[uriref_str_label] = subjects_df['subject'].apply(extract_uriref_str)
    # Well, and the next one is also series only because uriref_str_to_map can then be reused outside of apply context
    subjects_df[[map_predicate_label, map_object_label]] = subjects_df[uriref_str_label].apply(uriref_str_to_map)
    # Mnemonic is necessary for disaggregation logic that follows
    subjects_df[mnemonic_label] = subjects_df.apply(extract_mnemonic, axis=1)
    
    # Now that we have mnemonics generated, let's honor any increment requests
    disaggregated_subject_rows = []
    def collect_incremented_subject_uri(row): return collect_incremented_uri(row, 'subject', disaggregated_subject_rows)
    subjects_df = subjects_df.apply(collect_incremented_subject_uri, axis=1)
    del subjects_df  # to collect garbage right away
    # Creating new frame so that there is no duplication wih previous
    subjects_df = pd.DataFrame(disaggregated_subject_rows)
    # Let's regenerate cols above for simplicity now that rows are disaggregated
    subjects_df[uriref_str_label] = subjects_df['subject'].apply(extract_uriref_str)
    # Knowing TriplesMap name is necessary for UUID substitution at uriref_str_to_map and mnemonic extraction
    subjects_df[[triplesmap_label, uuid_label]] = subjects_df.apply(generate_triplesmap_name, axis=1)
    subjects_df[[map_predicate_label, map_object_label]] = subjects_df.apply(lambda row: uriref_str_to_map(row[uriref_str_label], row[uuid_label]), axis=1)
    subjects_df[mnemonic_label] = subjects_df.apply(extract_mnemonic, axis=1)
    # Now that all cols have been disaggregated, let's generate remaining useful cols
    subjects_df[rico_name_label] = subjects_df.apply(generate_rico_name, axis=1)
    # Let's drop the object (i.e., rdf:type) because it's now in rico_name_label
    subjects_df.drop(['object', uriref_str_label], axis=1, inplace=True)

    # Convert preprocessed DataFrame to HTML
    #from IPython.display import display, HTML, Markdown
    #sorted_columns = [triplesmap_label, rico_name_label, map_predicate_label, map_object_label, mnemonic_label, 'subject']
    #display_table = subjects_df[subjects_df[map_predicate_label].notnull()][sorted_columns].head(10).sort_values(by=triplesmap_label, ascending=True)
    #html_table = display_table.to_html(index=False) # for Jupyter Notebook
    #display(HTML(html_table)) # for Jupyter Notebook
    #print("\n\nSubjects Dataframe Preview:")
    #subjects_df.info()
    #print("\n", "\n\n".join([str(display_table.iloc[i]) for i in range(len(display_table))])) # debug
    
    # Add useful columns from subjects dataset for matching within loop later
    # The column name stays unique so we should just remember that RiC-O name refers to subject
    # The line below is really important, or triples will be lost!
    parsed_df = parsed_df.rename(columns={'subject': 'original_subject'}) 
    merge_cols = ['original_subject', 'subject', rico_name_label]
    if increment_number_label in subjects_df.columns:
        merge_cols.append(increment_number_label)
    parsed_df = pd.merge(parsed_df, subjects_df[merge_cols], on='original_subject', how='left')
    # The below line is necessary because np.nan in merged df force this col into float
    if increment_number_label in parsed_df.columns:
        parsed_df[increment_number_label] = parsed_df[increment_number_label].astype('Int64')
    #parsed_df[increment_number_label] = parsed_df[increment_number_label].astype(int)  # Convert to int
    #print(parsed_df[increment_number_label])
    # Also extract map predicates and objects for each object
    # Note that the below are for object, not subject, even though columns are called the same
    # Also note for next line that it is the only one that applies to series, all other to df
    parsed_df[uriref_str_label] = parsed_df['object'].apply(extract_uriref_str)
    # Well, and the next one is also series only because uriref_str_to_map can then be reused outside of apply context
    parsed_df[[map_predicate_label, map_object_label]] = parsed_df[uriref_str_label].apply(uriref_str_to_map)
    parsed_df[mnemonic_label] = parsed_df.apply(extract_mnemonic, axis=1)

    # Now that we have mnemonics generated, let's honor any increment requests
    disaggregated_object_rows = []
    def collect_incremented_object_uri(row): return collect_incremented_uri(row, 'object', disaggregated_object_rows)
    parsed_df = parsed_df.apply(collect_incremented_object_uri, axis=1)
    # Creating new frame so that there is no duplication wih previous
    parsed_df = pd.DataFrame(disaggregated_object_rows)
    # Let's regenerate cols above for simplicity now that rows are disaggregated
    parsed_df[uriref_str_label] = parsed_df['object'].apply(extract_uriref_str)
    # TriplesMap string will be necessary later on to filter out non-matching objects
    parsed_df[[triplesmap_label, uuid_label]] = parsed_df.apply(generate_triplesmap_name, axis=1)
    parsed_df[[map_predicate_label, map_object_label]] = parsed_df[uriref_str_label].apply(uriref_str_to_map)
    parsed_df[mnemonic_label] = parsed_df.apply(extract_mnemonic, axis=1)

    # Now that all cols have been disaggregated, drop the temporary field
    parsed_df.drop(uriref_str_label, axis=1, inplace=True)

    # Sort and only show those that have a predicate
    #display_table = parsed_df[parsed_df[uriref_str_label].notnull()].head(10).sort_values(by=triplesmap_label, ascending=True)
    #print("\n\nAll Triples Dataframe Preview:")
    #parsed_df.info()
    #print("\n", "\n\n".join([str(display_table.iloc[i]) for i in range(len(display_table))])) # debug

    # Define blank nodes and triples
    #agent_name_map = BNode()
    #agent_map = BNode()

    # Triples for :AgentNameAUTH13
    #mapping.add((maps[1].AgentNameAUTH13, RDF.type, rr[1].TriplesMap))

    # Additional RML masks
    iterator_mask = r'1'

    # This function is unused as long as URIs are hardcoded in draw.io graphs
    def construct_uri_mask(subjects_df, i):
        global mnemonic_label
        mnemonics = subjects_df.loc[:, mnemonic_label].tolist()
        subject_row = subjects_df.loc[i, :]
        rico_class = subject_row[rico_name_label][5:]
        #uri_mask = subject_row[uri_mask_label]
        try:
            if base_uri == base_auth_uri: # An Authority source
                if auth_heading_label in mnemonics:
                    uri_mask = f'{{{auth_heading_label}}}/{rico_class}/{iterator_mask}'
            elif base_uri == base_add_uri:
                if add_ref_add_label in mnemonics: # We have a LISTINGS source
                    if add_ref_file_label in mnemonics:
                        uri_mask = f'{{{add_ref_add_label}}}/{{{add_ref_file_label}}}/{rico_class}/{iterator_mask}'
                    else: # No Listings-level reference code
                        uri_mask = f'{{{add_ref_add_label}}}/{{{add_title_label}}}/{rico_class}/{iterator_mask}'
                elif add_refd_label in mnemonics: # We have a DESCRIPTION source
                    uri_mask = f'{{{add_refd_label}}}/{rico_class}/{iterator_mask}'
            
            return uri_mask
        except UnboundLocalError:
            print(f'No valid identifiers found for an ADD source:\n{subject_row}')
            return None
    
    # Initialize a mapping RDF graph
    mapping = Graph(base = URIRef(f"{base_gbad_uri}/"))
    
    # Define custom prefix
    maps = ('', Namespace(URIRef(f"{base_mapping_uri}#")))

    # Bind prefixes to namespaces
    mapping.namespace_manager.bind(*auth)
    mapping.namespace_manager.bind(*add)
    mapping.namespace_manager.bind(*rico)
    mapping.namespace_manager.bind(*rdf)
    mapping.namespace_manager.bind(*rdfs)
    mapping.namespace_manager.bind(*owl)
    mapping.namespace_manager.bind(*rml)
    mapping.namespace_manager.bind(*rr)
    mapping.namespace_manager.bind(*ql)
    mapping.namespace_manager.bind(*csvw)
    mapping.namespace_manager.bind(*maps)
    mapping.namespace_manager.bind(*fnml)
    mapping.namespace_manager.bind(*fno)
    mapping.namespace_manager.bind(*idlab_fn)
    mapping.namespace_manager.bind(*grel)

    def fno_map_value_unless_isnull(
            rml_g,
            return_tuple, input_tuples):
        return_predicate, return_object = return_tuple

        # Define a wrapper function
        fno_wrapper = BNode()

        # Use the controls_if function to conditionally map based on non-empty value
        controls_if_pomap = BNode()
        rml_g.add((fno_wrapper, rr[1].predicateObjectMap, controls_if_pomap))
        rml_g.add((controls_if_pomap, rr[1].predicate, fno[1].executes))
        controls_if_omap = BNode()
        rml_g.add((controls_if_pomap, rr[1].objectMap, controls_if_omap))
        rml_g.add((controls_if_omap, rr[1].constant, grel[1].controls_if))

        # Define the arguments for the if condition
        # First argument: Check if input value is empty
        mnemonic_isnull_pomap = BNode()
        rml_g.add((fno_wrapper, rr[1].predicateObjectMap, mnemonic_isnull_pomap))
        rml_g.add((mnemonic_isnull_pomap, rr[1].predicate, grel[1].bool_b))
        mnemonic_isnull_omap = BNode()
        rml_g.add((mnemonic_isnull_pomap, rr[1].objectMap, mnemonic_isnull_omap))
        # A nested function
        nested_fno_logic = BNode()
        rml_g.add((mnemonic_isnull_omap, fnml[1].functionValue, nested_fno_logic))
        # Nested function definition
        mnemonic_isnull_nested_def_pomap = BNode()
        rml_g.add((nested_fno_logic, rr[1].predicateObjectMap, mnemonic_isnull_nested_def_pomap))
        rml_g.add((mnemonic_isnull_nested_def_pomap, rr[1].predicate, fno[1].executes))
        mnemonic_isnull_nested_def_omap = BNode()
        rml_g.add((mnemonic_isnull_nested_def_pomap, rr[1].objectMap, mnemonic_isnull_nested_def_omap))
        rml_g.add((mnemonic_isnull_nested_def_omap, rr[1].constant, idlab_fn[1].isNull))
        # Nested function argument
        mnemonic_isnull_nested_arg_pomap = BNode()
        rml_g.add((nested_fno_logic, rr[1].predicateObjectMap, mnemonic_isnull_nested_arg_pomap))
        rml_g.add((mnemonic_isnull_nested_arg_pomap, rr[1].predicate, idlab_fn[1].str))
        mnemonic_isnull_nested_arg_omap = BNode()
        rml_g.add((mnemonic_isnull_nested_arg_pomap, rr[1].objectMap, mnemonic_isnull_nested_arg_omap))
        # Here goes the climax of checking - the input value
        for input_tuple in input_tuples:
            rml_g.add((mnemonic_isnull_nested_arg_omap, input_tuple[0], input_tuple[1]))

        # If the input value is not null, use the value in the object map
        mnemonic_uri_mask_pomap = BNode()
        rml_g.add((fno_wrapper, rr[1].predicateObjectMap, mnemonic_uri_mask_pomap))
        rml_g.add((mnemonic_uri_mask_pomap, rr[1].predicate, grel[1].any_false))
        mnemonic_uri_mask_omap = BNode()
        rml_g.add((mnemonic_uri_mask_pomap, rr[1].objectMap, mnemonic_uri_mask_omap))
        # Here goes the climax of writing - the return value
        rml_g.add((mnemonic_uri_mask_omap, return_predicate, return_object))
        
        return fno_wrapper
    
    def fno_map_this_string_match(
            rml_g,
            return_tuple, input_value_tuples, regex_tuples):
        # Define a wrapper function
        nested_fno_wrapper = BNode()
        # Nested function definition
        nested_def_pomap = BNode()
        rml_g.add((nested_fno_wrapper, rr[1].predicateObjectMap, nested_def_pomap))
        rml_g.add((nested_def_pomap, rr[1].predicate, fno[1].executes))
        nested_def_omap = BNode()
        rml_g.add((nested_def_pomap, rr[1].objectMap, nested_def_omap))
        rml_g.add((nested_def_omap, rr[1].constant, grel[1].string_match))

        # Nested function argument 1
        nested_fun_arg_1_pomap = BNode()
        rml_g.add((nested_fno_wrapper, rr[1].predicateObjectMap, nested_fun_arg_1_pomap))
        rml_g.add((nested_fun_arg_1_pomap, rr[1].predicate, grel[1].valueParameter))
        nested_fun_arg_1_omap = BNode()
        rml_g.add((nested_fun_arg_1_pomap, rr[1].objectMap, nested_fun_arg_1_omap))
        # Here goes the climax of checking - the input_value_1
        for input_value_tuple_1 in input_value_tuples:
            # Define a wrapper function
            nested_tostring_fno_wrapper = BNode()
            # Nested function definition
            nested_tostring_def_pomap = BNode()
            rml_g.add((nested_tostring_fno_wrapper, rr[1].predicateObjectMap, nested_tostring_def_pomap))
            rml_g.add((nested_tostring_def_pomap, rr[1].predicate, fno[1].executes))
            nested_tostring_def_omap = BNode()
            rml_g.add((nested_tostring_def_pomap, rr[1].objectMap, nested_tostring_def_omap))
            rml_g.add((nested_tostring_def_omap, rr[1].constant, grel[1].string_toString))
            # Nested function argument 1
            nested_tostring_fun_arg_1_pomap = BNode()
            rml_g.add((nested_tostring_fno_wrapper, rr[1].predicateObjectMap, nested_tostring_fun_arg_1_pomap))
            rml_g.add((nested_tostring_fun_arg_1_pomap, rr[1].predicate, grel[1].p_any_e))
            nested_tostring_fun_arg_1_omap = BNode()
            rml_g.add((nested_tostring_fun_arg_1_pomap, rr[1].objectMap, nested_tostring_fun_arg_1_omap))
            rml_g.add((nested_tostring_fun_arg_1_omap, input_value_tuple_1[0], input_value_tuple_1[1]))
            rml_g.add((nested_fun_arg_1_omap, fnml[1].functionValue, nested_tostring_fno_wrapper))
        
        # Nested function argument 2
        nested_fun_arg_2_pomap = BNode()
        rml_g.add((nested_fno_wrapper, rr[1].predicateObjectMap, nested_fun_arg_2_pomap))
        rml_g.add((nested_fun_arg_2_pomap, rr[1].predicate, grel[1].p_string_regex))
        nested_fun_arg_2_omap = BNode()
        rml_g.add((nested_fun_arg_2_pomap, rr[1].objectMap, nested_fun_arg_2_omap))
        # Here goes the climax of checking - the input_value_2
        for input_value_tuple_2 in regex_tuples:
            rml_g.add((nested_fun_arg_2_omap, input_value_tuple_2[0], input_value_tuple_2[1]))

        # Convert string match output to boolean
        input_tuples = [(fnml[1].functionValue, nested_fno_wrapper)]
        fno_wrapper = fno_map_value_unless_isnull(
            rml_g = rml_g,
            return_tuple = return_tuple,
            input_tuples = input_tuples)
        
        return fno_wrapper

    def add_custom_triple_to_triplesmap(predicate_uri, object_var, triples_map):
        # Define a predicate-object map
        predicate_object_map = BNode()
        mapping.add((triples_map, rr[1].predicateObjectMap, predicate_object_map))
        # Add predicate to predicate-object map
        mapping.add((predicate_object_map, rr[1].predicate, URIRef(predicate_uri)))
        # Define an empty object map within the predicate-object map
        object_map = BNode()
        mapping.add((predicate_object_map, rr[1].objectMap, object_map))
        # Add object to object map
        object = object_var if isinstance(object_var, URIRef) else Literal(object_var)
        mapping.add((object_map, rr[1].template, object))
        return None
    
    # Construct RML graph
    for i, subject_row in subjects_df.drop_duplicates().iterrows():  # not sure why but drop dupes is needed now after adding support for multiple incremented mnemonics
        # This refers to the original subject URI from drawio graph
        # which is being used to uniquely identify subject
        subject_uri = subject_row['subject']
        subject_mnemonic = subject_row[mnemonic_label]

        # Skip private fields removed from input data
        if subject_mnemonic in private_mnemonics:
            continue

        # Define TriplesMap
        triplesmap_name = subject_row[triplesmap_label]
        triples_map = maps[1][triplesmap_name]
        mapping.add((triples_map, RDF.type, rr[1].TriplesMap))

        # Define Logical Source
        logical_source = BNode()
        mapping.add((triples_map, rml[1].logicalSource, logical_source))
        mapping.add((logical_source, rml[1].source, Literal(source_path)))
        mapping.add((logical_source, rml[1].referenceFormulation, ql[1].CSV))
        #mapping.add((logical_source, rml[1].iterator, Literal(iterator_mask)))

        # Collect subjectmap predicate and object from subject df
        # These will be added to the graph and then used later on
        authtp_column_name = None # only set for RICO_AUTHTP replaced subjects
        if subject_uri in rico_authtp_subjects.keys():
            true_subject_uri, authtp_column_name = rico_authtp_subjects[subject_uri]
            true_subject_po = uriref_str_to_map(extract_uriref_str(true_subject_uri),
                                                generate_uuid_str(triplesmap_name,
                                                                  show_message=False)) # already saw these UUIDs
            subject_map_predicate = true_subject_po[map_predicate_label]
            uri_mask = true_subject_po[map_object_label]
        else:
            subject_map_predicate = subject_row[map_predicate_label]
            uri_mask = subject_row[map_object_label]
        #URIRef(urllib.parse.unquote(str(subject)))
        #uri_mask = construct_uri_mask(subjects_df, i)
        
        # Define an empty Subject Map
        subject_map = BNode()
        mapping.add((triples_map, rr[1].subjectMap, subject_map))

        # This is when you simply want to port originals
        def add_all_po_for_s(subject_uri):
            owl_objectmap_df = parsed_df[(
                (parsed_df['original_subject']==subject_uri)
            )]
            for k, parsed_result in owl_objectmap_df.iterrows():
                # Only allow RDFS predicates for now
                predicate = parsed_result['predicate']
                norm_predicate = normalize_uri(predicate, mapping.namespace_manager)
                is_rico = (norm_predicate.startswith(f"{rico[0]}:"))
                is_rdfs = (norm_predicate.startswith(f"{rdfs[0]}:"))
                is_auth = (norm_predicate.startswith(f"{auth[0]}:"))
                is_add = (norm_predicate.startswith(f"{add[0]}:"))
                if (is_rico | is_rdfs | is_auth | is_add):
                    # Now we can actually iterate over objects
                    object = parsed_result['original_object']
                    predicate_object_map = BNode()
                    pom_create_triple = (triples_map, rr[1].predicateObjectMap, predicate_object_map)
                    mapping.add(pom_create_triple)

                    # Add predicate to predicate-object map
                    pom_predicate_triple = (predicate_object_map, rr[1].predicate, predicate)
                    mapping.add(pom_predicate_triple)

                    # Add object to predicate-object map
                    if isinstance(object, Literal):
                        object_map = BNode()
                        mapping.add((predicate_object_map, rr[1].objectMap, object_map))
                        mapping.add((object_map, rr[1].constant, Literal(object.value)))
                        if object.language:
                            mapping.add((object_map, rr[1].language, Literal(object.language)))
                    else:
                        mapping.add((predicate_object_map, rr[1].object, object))

        # Remove prefix from RiC-O name from subject df and add to graph
        rico_name = subject_row[rico_name_label]
        rico_class = rico_name.split(':')[1]
        class_uri = rico[1][rico_class]
        for non_rico_class_uri in allowed_non_rico_classes:
            if rico_name == str(normalize_uri(non_rico_class_uri, mapping.namespace_manager)):
                class_uri = non_rico_class_uri
                add_all_po_for_s(subject_uri) # Preserve details for custom OWL datatype properties
                break
        # So this adds the rdf:type definition
        mapping.add((subject_map, rr[1]['class'], class_uri))

        # If no valid RML definitions in the graph
        if not subject_map_predicate:
            #if isinstance(triples_map, BNode):
            #    # Means that 
            #    continue
            # Replace the blank node with subject as literal
            # Well, this is not really a subject "uri" in this case
            # or shouldn't be because URIs have to be set up via rr:constant
            if subject_uri: # not sure if it is at all possible for this to be null
                mapping.add((subject_map, rr[1].constant, Literal(subject_uri)))
            continue # because cannot move forward with map predicate undefined
            # Also note that rr:subject is incompatible with logical source

        if not subject_mnemonic:
            # Add map predicate and object from df to subject map
            mapping.add((subject_map, subject_map_predicate, uri_mask))
        #
        # Now that we have handled all the no-mnemonic cases (both when no valid RML
        # syntax in the drawio graph AND when the syntax is there but no mnemonic
        # used), let's handle cases with both valid RML syntax and mnemonic set.
        #
        # We will use an FnO logic to leave subject maps empty at mapping
        # when the value of the source CSV column in empty.
        #
        # Here comes:
        else:
            input_tuples = [(rml[1].reference, Literal(subject_mnemonic))]
            return_tuple = (subject_map_predicate, uri_mask)
            fno_mnemonic_logic = fno_map_value_unless_isnull(
                    rml_g = mapping,
                    return_tuple = return_tuple,
                    input_tuples = input_tuples)
            
            # IMPORTANT! Note that the below only executes if mnemonic is set in drawio,
            # so for entities defined as constants RICO_AUTHTP will be bugged
            if authtp_column_name:
                rico_authtp_uri_term, authtp_value = rico_authtp_dict[rico_class]
                authtp_column_tuples = [(rml[1].reference, Literal(authtp_column_name))]
                authtp_value_tuples = [(rr[1].template, Literal(authtp_value)),
                                        (rr[1].termType, rr[1].Literal)]
                return_tuple = (fnml[1].functionValue, fno_mnemonic_logic)
                rico_authtp_string_match = fno_map_this_string_match(
                    rml_g = mapping,
                    return_tuple = return_tuple,
                    input_value_tuples = authtp_column_tuples,
                    regex_tuples = authtp_value_tuples)
                mapping.add((subject_map, fnml[1].functionValue, rico_authtp_string_match))
            else:
                mapping.add((subject_map, fnml[1].functionValue, fno_mnemonic_logic))

        # Record source mnemonic as a triple
        # Commenting out for now because not sure yet
        # how exactly in RDF we want this implemented
        #if subject_mnemonic:
        #    mnemonic_schema_uri = URIRef(f"{str(base_schema_uri)}/{get_second_term()}/Mnemonic/{subject_mnemonic}")
        #    predicate_for_old_mnemonic = rico[1].hasOrHadIdentifier
        #    add_custom_triple_to_triplesmap(predicate_for_old_mnemonic, mnemonic_schema_uri, triples_map)

        # Deal with predicates and objects in full triples df
        # Subset triples with the subject and RiC-O class from i-loop
        objectmap_df = parsed_df[(
            (parsed_df['subject']==subject_uri) &
            (parsed_df[rico_name_label] == rico_name)
        )]
        
        # Auto-generate rdfs:label when not set in drawio
        has_rdfs_label = (objectmap_df.loc[:, 'predicate'] == rdfs[1].label).any()
        if not has_rdfs_label:
            # Define a predicate-object map
            predicate_object_map = BNode()
            pom_create_triple = (triples_map, rr[1].predicateObjectMap, predicate_object_map)
            mapping.add(pom_create_triple)

            # Add predicate to predicate-object map
            pom_predicate_triple = (predicate_object_map, rr[1].predicate, rdfs[1].label)
            mapping.add(pom_predicate_triple)

            # Define an empty object map within the predicate-object map
            object_map = BNode()
            om_create_triple = (predicate_object_map, rr[1].objectMap, object_map)
            mapping.add(om_create_triple)

            # Generate rdfs:label from uri_mask
            mapping.add((object_map, rr[1].termType, rr[1].Literal)) # print as literal
            pretty_omo = prettify_rdfs_label(uri_mask)
            rdfs_label_triple = (object_map, rr[1].template, Literal(pretty_omo))
            mapping.add(rdfs_label_triple)
        
        # Now finally iterate over all predicates and objects
        for k, parsed_result in objectmap_df.iterrows():
            # Only focus on RiC-O or RDFS predicates
            predicate = parsed_result['predicate']
            norm_predicate = normalize_uri(predicate, mapping.namespace_manager)
            is_rico = (norm_predicate.startswith(f"{rico[0]}:"))
            is_rdfs = (norm_predicate.startswith(f"{rdfs[0]}:"))
            is_auth = (norm_predicate.startswith(f"{auth[0]}:"))
            is_add = (norm_predicate.startswith(f"{add[0]}:"))
            if (is_rico | is_rdfs | is_auth | is_add):
                # Now we can actually iterate over objects
                object = parsed_result['object']
                original_object = parsed_result['original_object']
                if object in rico_authtp_subjects.keys(): # checking if the object is a subject among rico_authtp_subjects
                    true_object_uri, authtp_column_name = rico_authtp_subjects[object]
                    true_object_po = uriref_str_to_map(extract_uriref_str(true_object_uri),
                                                        generate_uuid_str(triplesmap_name, # subject triplesmap
                                                                          show_message=False)) # already saw these UUIDs
                    object_map_predicate = true_object_po[map_predicate_label]
                    object_map_object = true_object_po[map_object_label]
                else: # Still do UUID replacement
                    object_po = uriref_str_to_map(extract_uriref_str(object),
                                                    generate_uuid_str(triplesmap_name, # subject triplesmap
                                                                        show_message=False)) # already saw these UUIDs
                    object_map_predicate = object_po[map_predicate_label]
                    object_map_object = object_po[map_object_label]
                object_mnemonic = parsed_result[mnemonic_label]
                #rdfs_label_triple = None # to use later - commented out since --label-disable

                # Support empty literal nodes - e.g., to
                # forcefully discard rdfs:label generation
                if object_map_object is None:
                    continue

                # Handle possible increment requests in object mnemonic
                object_mnemonic_i_from, object_mnemonic_i_to = get_mnemonic_i_from_to(object_mnemonic)
                for object_mnemonic_i in range(object_mnemonic_i_from, object_mnemonic_i_to + 1):
                    #if (parsed_result['original_subject']==subject_row['original_subject'] and
                    #    object_mnemonic != subject_mnemonic):
                    #    continue
                    # Define a predicate-object map
                    predicate_object_map = BNode()
                    pom_create_triple = (triples_map, rr[1].predicateObjectMap, predicate_object_map)
                    mapping.add(pom_create_triple)

                    # Add predicate to predicate-object map
                    pom_predicate_triple = (predicate_object_map, rr[1].predicate, URIRef(predicate))
                    mapping.add(pom_predicate_triple)

                    # Define an empty object map within the predicate-object map
                    object_map = BNode()
                    om_create_triple = (predicate_object_map, rr[1].objectMap, object_map)
                    mapping.add(om_create_triple)

                    # If not RiC-O, then nothing applies and just attach as literal
                    # In the current version of drawio parser only rdfs:label is supported
                    # and such, so this is essential to bypass these. However, I am not
                    # sure at this point how well this would work if other namespaces
                    # were fully supported by drawio parser.
                    if not is_rico: # any other namespace
                        if norm_predicate == 'rdfs:label': # handle labels from drawio parser
                            # Legacy code commented out since --label-disable
                            #if rdfs_label_triple: # already added - remove empty nodes and continue
                            #    mapping.remove(pom_create_triple)
                            #    mapping.remove(pom_predicate_triple)
                            #    mapping.remove(om_create_triple)
                            #else:
                            mapping.add((object_map, rr[1].termType, rr[1].Literal)) # print as literal
                            # The below line is for cases when neither rr predicate is found in the drawio node (so omp is None)
                            rdfs_label_rr_predicate = object_map_predicate if object_map_predicate else rr[1].constant
                            rdfs_label_triple = (object_map, URIRef(rdfs_label_rr_predicate), Literal(object_map_object))
                            mapping.add(rdfs_label_triple)
                            continue    

                    # This concerns only constant literals, meaning nodes
                    # in drawio graph for which no mapping logic is defined
                    if not object_map_predicate:
                        # So these are simply added as predicate and object, no predicate-object map
                        if object_map_object: # sometimes it may be empty
                            mapping.add((object_map, rr[1].constant, object_map_object)) 
                        else:
                            mapping.add((object_map, rr[1].constant, Literal(object))) # point to constant URI
                        continue
                    
                    # Now let's finally attach the object to the object map
                    # Case when the object is supposed to reference another Subject map
                    if object in set(subjects_df['subject']):
                        triplesmap = maps[1][subjects_df[subjects_df['subject']==object][triplesmap_label].iloc[0]]
                        mapping.add((object_map, rr[1].parentTriplesMap, triplesmap))
                        #join_condition = BNode()
                        #mapping.add((object_map, rr[1].joinCondition, join_condition))
                        #mnemonic = parsed_result[mnemonic_label]
                        #mapping.add((join_condition, rr[1].child, Literal(mnemonic)))
                        #mapping.add((join_condition, rr[1].parent, Literal(mnemonic)))
                    else:
                        object_mnemonic_ith = mnemonic_i_regex.sub(str(object_mnemonic_i), object_mnemonic) if object_mnemonic_i_to > 1 else object_mnemonic
                        # Well, the below does seem to work but may be a bad idea because object's mnemonic
                        # does not necessarily have to match subject's mnemonic (what if they are separate increments?)
                        # Thus, I commented out that block
                        #if ((object != original_object) and # means it is one of the disaggregated ones
                        #    (str(object_mnemonic_ith) != str(subject_mnemonic))): # mismatched phantoms - remove empty nodes and continue
                        #    mapping.remove(pom_create_triple)
                        #    mapping.remove(pom_predicate_triple)
                        #    mapping.remove(om_create_triple)
                        #    continue
                        if object_mnemonic_ith in private_mnemonics:
                            mapping.add((object_map, rr[1].constant, URIRef(f"censored#{object_mnemonic_ith}")))
                            continue
                        object_map_predicate = parsed_result[map_predicate_label]
                        object_map_object = parsed_result[map_object_label]
                        if object_map_object: # just in case user forgot to set it in drawio
                            # Logic to substitute increment request with an actual number for object
                            object_map_object_ith = mnemonic_i_regex.sub(str(object_mnemonic_i), str(object_map_object)) if object_mnemonic_i_to > 1 else str(object_map_object)
                            object_map_object_ith = URIRef(object_map_object_ith) if isinstance(object_map_object_ith, URIRef) else Literal(object_map_object_ith)
                            mapping.add((object_map, object_map_predicate, object_map_object_ith))

    # Serialize and print the RDF graph
    ttl = mapping.serialize(format='turtle')
    os.makedirs(os.path.dirname(rml_path), exist_ok=True)
    with open(rml_path, 'w') as f:
        f.write(ttl)
    print(f"\n\nSuccessfully saved RML map to: '{rml_path}'")
    #print(ttl)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Map schema of choice")
    parser.add_argument("schema", help="Choose one: add or auth.")
    parser.add_argument("source", nargs='?', help="Filename of source CSV without extension. Defaults to the head=6 version for chosen schema.")

    args = parser.parse_args()

    __init__(str(args.schema).lower(), args.source)
