# Originally generated with ChatGPT-4o on 2024-08-23,
# with subsequent modifications

import os
#import sys
import glob
import subprocess
#import hashlib
from rdflib import Graph, Namespace, URIRef, Literal, BNode
from rdflib.namespace import RDF, RDFS, OWL, DCTERMS, NamespaceManager
from pprint import pprint
import argparse
import shutil
from io import BytesIO
import re

BASE_URI = 'https://data.archives.gov.on.test.gbad.ca/'

def map_rml(schema_code, rml_path=None):
    """
    Returns a tuple of (rml, rmlmapper, ttl) paths.
    """

    # Define directories
    if schema_code == 'add':
        rml_dir = "gbad/schema/description-listings"
    elif schema_code == 'auth':
        rml_dir = "gbad/schema/authority"
    else:
        raise Exception(f"Fatal error: Schema code not supplied.")
    
    rml_files = []
    if rml_path:  # Assume it is relative to rml_dir
        try_rml_subdir = os.path.join(os.path.normpath(rml_dir),
                                      os.path.normpath(rml_path))
        if os.path.isdir(try_rml_subdir):
            rml_dir = try_rml_subdir
        else:  # this is actually a path to RML file
            rml_files.append(try_rml_subdir)
    
    ttl_root = "gbad/mapping/target"
    #rmlmapper_dir = "riconverted_general_authority_to_ric-o_model_2024-11-25_pz"
    rmlmapper_dir = "."

    # Find the .rml file
    if len(rml_files) == 0:
        rml_files = glob.glob(os.path.join(os.path.normpath(rml_dir), "*.rml"))

    return_tuple = (None, None, None)
    if (rml_files):
        rml = rml_files[0]  # Assuming you want the first .rml file found
        rml_filename = os.path.splitext(os.path.basename(rml))[0]

        # Create target directory if it does not exist
        ttl_dir = os.path.join(os.path.normpath(ttl_root), rml_filename)
        os.makedirs(ttl_dir, exist_ok=True)
        
        # Define the output file
        mapped_filename = "mapped.ttl"
        ttl = os.path.join(ttl_dir, mapped_filename)

        if os.path.exists(ttl):
            mapped_backup_filename = "mapped.ttl.backup"
            ttl_backup = os.path.join(ttl_dir, mapped_backup_filename)
            try:
                #os.rename(ttl, ttl_backup)
                shutil.copy2(ttl, ttl_backup)
                print(f"File '{mapped_filename}' already exists - copied to '{mapped_backup_filename}'")
            except PermissionError:
                print(f"Aborted: File '{mapped_filename}' already exists and cannot be renamed for backup due to a permission error.")

        def extract_source_csv_path(rml_path):
            try:
                print("Trying to extract source CSV path from RML...")
                with open(rml_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                pattern = r'rml:source "(gbad/mapping/source/(.+).csv)"'
                match = re.search(pattern, content)

                if match:
                    source_csv_path = match.group(1)
                    source_csv_filename = os.path.splitext(os.path.basename(source_csv_path))[0]
                    print(f"Extracted rml:source path: '{source_csv_path}'")
                    return (source_csv_path, source_csv_filename)
                else:
                    raise Exception(f"Error: rml:source not found in the RML file.")
            except FileNotFoundError:
                print(f"Error: File '{rml_path}' not found.")
                return (None, None)
            except Exception as e:
                print(f"Error: {e}")
                return (None, None)

        source_csv_path, source_csv_filename = extract_source_csv_path(rml)
        if source_csv_filename:
            subdir = os.path.join(ttl_dir, source_csv_filename)
            os.makedirs(subdir, exist_ok=True)
            ttl = os.path.join(subdir, mapped_filename)

        def map_using_rmlmapper(rml, ttl):
            """Run the RMLMapper Java command."""
            nonlocal rmlmapper_dir
            rmlmapper_files = glob.glob(os.path.join(os.path.normpath(rmlmapper_dir), "rmlmapper*"))
            
            if (rml_files and rmlmapper_files):
                rmlmapper = rmlmapper_files[0] # Same assumption for mapper jar
            else:
                raise Exception("No mapper file found in specified path.")

            return_tuple = (rml, rmlmapper, ttl)
            print("Initiated mapping params:")
            pprint(return_tuple)

            java_command = [
                "java", "-jar", rmlmapper,
                "-s", "turtle",
                "-m", rml,
                "-o", ttl,
                "-b", BASE_URI[:-1]
            ]
            try:
                print(f"\n\nRunning Java command: '{" ".join(java_command)}'\n\n")
                subprocess.run(java_command, check=True, capture_output=True, text=True)
            # Catch CalledProcessError specifically for command failures
            except subprocess.CalledProcessError as e:
                print(f"Failed to run mapper jar (exit code: {e.returncode}):")
                print(f"Command: {e.cmd}")
                if e.stdout:
                    print(f"STDOUT:\n{e.stdout}")
                if e.stderr:
                    print(f"STDERR:\n{e.stderr}")
                # You can re-raise the exception if you want to propagate it after logging
                raise
            except Exception as e:
                print(f"Failed to run mapper jar: '{e}'")
                raise
            return return_tuple

        def map_using_pyrml(rml, ttl):
            """Create an instance of RML Mapper with PyRML."""
            raise NotImplementedError()
            return_tuple = (rml, 'pyrml', ttl)
            print("Initiated mapping params:")
            pprint(return_tuple)

            try:
                from pyrml import PyRML
                mapper = PyRML.get_mapper()
                mapped_graph = mapper.convert(rml)
                mapped = mapped_graph.serialize(format='turtle')
                os.makedirs(os.path.dirname(ttl), exist_ok=True)
                with open(ttl, 'w') as f:
                    f.write(mapped)
            except Exception as e:
                print(f"Failed to map using pyrml: '{e}'")
                raise
            return return_tuple
        
        try:
            return_tuple = map_using_rmlmapper(rml, ttl)
            #return_tuple = map_using_pyrml(rml, ttl)
            rml, rmlmapper, ttl = return_tuple
            if os.path.exists(ttl):
                file_size_bytes = os.path.getsize(ttl)
                file_size_mb = file_size_bytes / (1024 * 1024)

                if file_size_mb > 10:
                    print(f"Converted file is larger than 10 MB ({file_size_mb:.2f} MB) - trying to rename to LARGE...")
                    try:
                        mapped_large_filename = "mapped_LARGE.ttl"
                        large_ttl = os.path.join(os.path.dirname(ttl), mapped_large_filename)
                        os.rename(ttl, large_ttl)
                        print(f"Successfully renamed to '{mapped_large_filename}'")
                        # Update returned params
                        ttl = large_ttl
                        return_tuple = (rml, rmlmapper, ttl)
                    except PermissionError:
                        print(f"Aborted: Could not rename due to a permission error.")
                else:
                    pass
            print(f"Successfully mapped '{rml}' to '{ttl}'\n")
        except Exception as e:
            print(f"\n\nException occurred: {e}\n\n")
    else:
        print("No .rml file found in specified path.")
    
    return return_tuple
    
def postprocess(graph_path):
    # Create the input RDF graph
    base_kb_uri = URIRef(os.path.join(BASE_URI, "KB"))
    base_schema_uri = URIRef(os.path.join(BASE_URI, "Schema"))
    base_auth_uri = URIRef(os.path.join(base_schema_uri, "Authority"))
    base_add_uri = URIRef(os.path.join(base_schema_uri, "Description-Listings"))
    base_mapping_uri = URIRef(os.path.join(base_schema_uri, "Mapping"))
    format = 'turtle'  # Adjust the format as needed
    g = Graph()

    # Define custom prefixes
    rico_uri = 'https://www.ica.org/standards/RiC/ontology#'
    rico = ('rico', Namespace(rico_uri))
    ns = ('', Namespace(BASE_URI))
    auth = ('auth', Namespace(f"{base_auth_uri}/"))
    add = ('add', Namespace(f"{base_add_uri}/"))

    # Define common prefixes
    rdf = ('rdf', RDF)
    rdfs = ('rdfs', RDFS)
    owl = ('owl', OWL)

    total_count = 0
    def print_total_count(): print(f"\nNumber of triples in the graph: {total_count}")

    print("Initiating postprocessing...")
    try:    
        g.parse(graph_path,
                format=format,
                publicID=BASE_URI[:-1])
        total_count = len(g)
        print(f"Successfully read a graph from '{graph_path}'")
        print_total_count()
        #print(g.serialize(format='turtle')) # debug
    except Exception as e:
        print(f"Failed to read graph from '{graph_path}'",
              f"\nError: '{e}'")
        
    # Bind prefixes to namespaces
    g.namespace_manager.bind(*rico)
    g.namespace_manager.bind(*ns, replace=True) # otherwise defaults to mapping
    g.namespace_manager.bind(*rdf)
    g.namespace_manager.bind(*rdfs)
    g.namespace_manager.bind(*owl)

    # Iterate over namespaces
    #for prefix, uri in g.namespace_manager.namespaces():
    #    print(f"Prefix: {prefix}, URI: {uri}")

    def save_removed_triples(graph_path, removed_graph, removed_count, pseudo_sparql, removed_triples_output_format, removed_triples_output_encoding):
        print("Executed a parametrized alternative of the following query:", pseudo_sparql)
        if removed_count > 0:
            ttl_filename = os.path.basename(graph_path)
            removed_triples_filename = f'{ttl_filename[:-4]}_removed_triples.{removed_triples_output_format}'
            removed_list_path = os.path.join(os.path.dirname(graph_path), removed_triples_filename)
            removed_graph.serialize(destination=removed_list_path,
                                    format=removed_triples_output_format,
                                    encoding=removed_triples_output_encoding)
            was_or_were = " was" if removed_count == 1 else "s were"
            print(f"{removed_count} triple{was_or_were} removed and dumped to: '{removed_list_path}'")
        else:
            print(f"No triples were removed.")

    def remove_false_agentcontrolrelation(g: Graph):
        # Parametrized query to find all rico:AgentControlRelation instances that are not
        # objects of rico:thingIsSourceOfRelation (empty, false entities generated from
        # drawio logic), and remove any triples where these are subjects or objects
        triples_to_remove = []
        removed_graph = Graph()
        removed_triples_output_format = 'nt'
        removed_triples_output_encoding = 'utf-8'
        removed_list_path = os.path.join(os.path.dirname(graph_path), 'removed_triples.nt')
        for s, p, o in g.triples((None, RDF.type, rico[1].AgentControlRelation)):
            if not (s, None, None) in g.triples((None, rico[1].thingIsSourceOfRelation, s)):
                for triple in g.triples((s, None, None)):
                    triples_to_remove.append(triple)
                # This part below is not needed really because none should exist
                #for triple in g.triples((s, None, None)):
                #   triples_to_remove.append(triple)
        removed_count = len(triples_to_remove)
        for triple in triples_to_remove:
            g.remove(triple)
            #print(*triple)
            removed_graph.add(triple)
        pseudo_sparql = """
        PREFIX rico: <{}>

        DELETE WHERE {
            ?s a rico:AgentControlRelation .
            FILTER NOT EXISTS {
                ?subject rico:thingIsSourceOfRelation ?s .
            }
        }
        """.format(rico_uri) # generated with ChatGPT based on parametrized
        save_removed_triples(graph_path, removed_graph, removed_count, pseudo_sparql, removed_triples_output_format, removed_triples_output_encoding)
        return removed_count
    
    def remove_false_authtp(g: Graph):
        # Set config
        triples_to_remove = []
        removed_graph = Graph()
        removed_triples_output_format = 'nt'
        removed_triples_output_encoding = 'utf-8'
        pseudo_sparql = """
        PREFIX rico: <{}>
        PREFIX authtp: <{}/AuthorityType#>
        DELETE WHERE {
            ?s1 rico:hasOrHadCorporateBodyType authtp:Geographic%20Name .
            ?s2 rico:hasOrHadCorporateBodyType authtp:Family%20Name .
            ?s3 rico:hasOrHadCorporateBodyType authtp:Personal%20Name .
            authtp:Geographic%20Name ?p1 ?o1 .
            authtp:Family%20Name ?p2 ?o2 .
            authtp:Personal%20Name ?p3 ?o3 .
        }
        """.format(rico_uri, base_auth_uri)

        # Run parametrized query
        authtp = ('authtp', Namespace(URIRef(f"{base_auth_uri}/AuthorityType#")))
        g.namespace_manager.bind(*authtp)
        authtp_list = [
            authtp[1]['Geographic%20Name'],
            authtp[1]['Family%20Name'],
            authtp[1]['Personal%20Name']
        ]
        for authtp_name in authtp_list:
            for s, p, o in g.triples((None, rico[1].hasOrHadCorporateBodyType, authtp_name)):
                triples_to_remove.append((s, p, o))
            for s, p, o in g.triples((authtp_name, None, None)):
                triples_to_remove.append((s, p, o))
        removed_count = len(triples_to_remove)
        for triple in triples_to_remove:
            g.remove(triple)
            #print(*triple)
            removed_graph.add(triple)

        # Save removed triples
        save_removed_triples(graph_path, removed_graph, removed_count, pseudo_sparql, removed_triples_output_format, removed_triples_output_encoding)
        return removed_count
    
    def remove_shorter_duplicate_labels(g: Graph):
        # Function originally generated with Claude 3.7 Sonnet on 2025-03-18, modified
        # Initial prompt:
        # below is an example of a set of triples with duplicate rdfs label. write me a sparql query that will iterate over all rico:recordset, find those that have 2 labels, get the literal value of their CurrentReferenceCode identifier, then see if indeed both labels start with it, and if yes, remove the label which is shorter. use the most efficient yet straightforward sparql strategy without overcomplicating syntax {selected triples for C 119 (Record Set)}
        # Follow-up prompt:
        # rewrite this line and only it "# Extract just the literal value of the reference code from its URI" so that it instead took the value of rdfs:label associated with the CurrentReferenceCode entity, which will be in the format: "{ref code literal} (Current Reference Code)". also, here is the correct uri for current reference code type: @prefix add: <https://data.archives.gov.on.ca/Schema/Description-Listings/> . add:CurrentReferenceCode
        # Concluding prompt:
        # ok. now pls rewrite it accurately, preserving all functionality intact, in parametrized format to conform with this example below: {def remove_false_authtp(g) and def run_postprocessing()}

        # Set config
        triples_to_remove = []
        removed_graph = Graph()
        removed_triples_output_format = 'nt'
        removed_triples_output_encoding = 'utf-8'

        curr_ref_code_label_pattern = r'^(.*) \(Current Reference Code\)$'
        pseudo_sparql = """
        PREFIX {}: <{}>
        PREFIX {}: <{}>
        PREFIX {}: <{}>
        """.format(rico[0], rico[1], rdfs[0], rdfs[1], add[0], add[1]) + """
        DELETE {
        ?recordSet rdfs:label ?shorterLabel .
        }
        WHERE {
        ?recordSet a rico:RecordSet ;
                    rdfs:label ?label1, ?label2 .
        FILTER(?label1 != ?label2)
        ?recordSet rico:hasOrHadIdentifier ?identifier .
        ?identifier a add:CurrentReferenceCode .
        ?identifier rdfs:label ?identLabel .""" + f"""
        BIND(REPLACE(?identLabel, "{curr_ref_code_label_pattern}", "$1") AS ?refCode)""" + """
        FILTER(STRSTARTS(?label1, ?refCode) && STRSTARTS(?label2, ?refCode))
        BIND(IF(STRLEN(?label1) < STRLEN(?label2), ?label1, ?label2) AS ?shorterLabel)
        }
        """
        
        g.namespace_manager.bind(*rico)
        g.namespace_manager.bind(*rdfs)
        g.namespace_manager.bind(*add)
        
        # Find all RecordSets
        record_sets = set()
        for s, p, o in g.triples((None, RDF.type, rico[1].RecordSet)):
            record_sets.add(s)
        
        # Process each RecordSet
        for rs in record_sets:
            # Get all labels for this RecordSet
            labels = []
            for s, p, o in g.triples((rs, RDFS.label, None)):
                if isinstance(o, Literal):
                    labels.append(o)
            
            # Skip if not exactly 2 labels
            if len(labels) != 2:
                continue
            
            # Get the identifier
            ref_code = None
            for s, p, o in g.triples((rs, rico[1].hasOrHadIdentifier, None)):
                # Check if it's a CurrentReferenceCode
                if (o, rico[1].hasIdentifierType, add[1].CurrentReferenceCode) in g:
                    # Get the label of the identifier
                    for s2, p2, o2 in g.triples((o, RDFS.label, None)):
                        if isinstance(o2, Literal):
                            # Extract the reference code from the label
                            ref_code_match = re.match(curr_ref_code_label_pattern, str(o2))
                            if ref_code_match:
                                ref_code = ref_code_match.group(1)
                                break
            
            # Skip if no reference code found
            if not ref_code:
                continue
            
            # Check if both labels start with the reference code
            label1, label2 = labels
            if str(label1).startswith(ref_code) and str(label2).startswith(ref_code):
                # Determine which label is shorter
                if len(str(label1)) < len(str(label2)):
                    shorter_label = label1
                else:
                    shorter_label = label2
                
                # Add to removal list
                triples_to_remove.append((rs, RDFS.label, shorter_label))
        
        # Remove the triples
        removed_count = len(triples_to_remove)
        for triple in triples_to_remove:
            g.remove(triple)
            removed_graph.add(triple)
        
        # Save removed triples
        save_removed_triples(graph_path, removed_graph, removed_count, pseudo_sparql, removed_triples_output_format, removed_triples_output_encoding)
        return removed_count

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
                        print(f"\nAdding a supplemental '{format_name}' file: '{file_path}'")
                        
                        # Parse the Turtle file and add its contents to the combined graph
                        source_graph.parse(file_path, format=format)

        filenames = (filename for filename in os.listdir(root_folder) if os.path.isfile(os.path.join(root_folder, filename)))
        walk_root_folder(root_folder, filenames)

        return source_graph

    def run_postprocessing():
        nonlocal total_count, g
        original_set = set(g)
        print("Postprocessing...")
        total_count = total_count - remove_shorter_duplicate_labels(g)
        #total_count = total_count - remove_false_agentcontrolrelation(g)
        #total_count = total_count - remove_false_authtp(g)
        #print("No postprocessing scheduled - none applied.")
        # Add additional triples
        if suppl_graph_dir:
            g = add_suppl_triples(g, suppl_graph_dir, format="turtle")
        print_total_count()
        return set(g) != original_set
    has_changed = run_postprocessing()

    return g, has_changed

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Map schema of choice")
    parser.add_argument("schema", help="Choose one: add or auth.")
    parser.add_argument("rml_path", nargs='?', help="Optional path to an RML file")

    args = parser.parse_args()

    suppl_graph_dir = 'gbad/schema' # to add any standalone ttls in schema dir

    rml_path, rmlmapper_path, ttl_path = map_rml(str(args.schema).lower(), str(args.rml_path).lower())
    graph, has_changed = postprocess(ttl_path)

    def save_postprocessed_graph(
            output_format = 'nt', # assumed to be quickest
            ttl_path = ttl_path):
        # Serialize and print the RDF graph
        #output_format = 'ttl' # more lightweight and readable
        output_encoding = 'utf-8' # just to be sure
        ttl_filename = os.path.basename(ttl_path)
        postprocessed_filename = f'{ttl_filename[:-4]}_postprocessed.{output_format}'
        postprocessed_path = os.path.join(os.path.dirname(ttl_path), postprocessed_filename)
        #postprocessed_serialized = graph.serialize(format=output_format)
        # FYI, serialize returns:
        # bytes if destination is None and encoding is not None.
        # str if destination is None and encoding is None.
        #with open(postprocessed_path, 'w') as f:
        #    f.write(postprocessed_serialized)
        # Output to memory for speed
        postprocessed_serialized = BytesIO()
        graph.serialize(destination=postprocessed_serialized,
                        format=output_format,
                        encoding=output_encoding)
        # Save to a file from BytesIO
        with open(postprocessed_path, 'wb') as f: # Use 'wb' for binary write mode
            f.write(postprocessed_serialized.getvalue())
        print(f"\n\nSuccessfully saved postprocessed graph at: '{postprocessed_path}'")
        return postprocessed_serialized
    
    if has_changed:
        postprocessed_ttl_content = save_postprocessed_graph()
    #print(postprocessed_ttl_content)
