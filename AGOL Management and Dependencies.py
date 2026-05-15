#!/usr/bin/env python
# coding: utf-8

# # AGOL Content Management, Tracking and Dependency Monitoring
# This script was initially taken from https://github.com/AlderMaps/arcgis-api-python/blob/main/AGOL_Monitoring_Dependencies.ipynb, and has been modified.
# 
# 
# 

# ## Project Intention
# <hr>
# I don't know about you, but monitoring content in ArcGIS Online for my organization has become a full time job. I want to spend less time tracking down items, figuring out what has been updated, and what needs to be reviewed. This project started as an answer to the million dollar problem of: how do we track which content items have been reviewed for accessibility and ADA compliance per the Section 504 regulations with an April 2027 (formerly 2026) deadline. In our organization we have over 4,000 content items and 30 users, and I was feeling like a deer in the headlights -- not just with how to begin, but how to track our progress and mark items as reviewed and meeting the WCAG standards. I am not an accessibility expert, I am not a project management or data management expert, and certainly not a coding expert, but I do like to find creative solutions for problems in the softwares I am familiar with -- namely, ArcGIS Online. 
# 
# One consideration I had when noodling about how to solve this problem: I want to reduce duplication of effort, and since so many of our ArcGIS Online items are nested in one way or another (feature layer --> Web Map --> Dashboard --> Experience Builder --> Hub Site), I wanted to be able to easily look at upstream or downstream dependent items when reviewing anything for ADA accessibility. Hence, I found the beautiful gitHub script linked above. This script did work, however it took over a week to run. I am sure there are methods of running scripts that would have significantly reduced that time, but like I said, I am not an expert so I'm working with what I know. 
# 
# For a while I worked off of the static layer created from that script, and included a dashboard/survey123 paired with a google form checklist to start tracking ADA (maybe I'll add some details about that later but it's not the main intention of this script), but I wanted the ability to quickly and easily update the item information as people review/change/delete content. I think this actually exists within ArcGIS Monitor, but I don't have that and I don't think it works outside of Portal. So that brings me to here, with a quick shout-out to my organization's Esri Solution Engineer, Will Delany, who pointed me towards [itemgraphs](https://developers.arcgis.com/python/latest/api-reference/arcgis.apps.itemgraph.html), which proved essential in speeding up my script runtime. It still takes an hour or two to run on my organizations 4,000+ items, but that is still WAY better than a week. 
# 

# ### Desired Outcomes
# So, what is it that I actually want from this script? 
# - A hosted feature layer/table with all my AGOL Content including information about:
#   - Item Name
#   - Item ID
#   - Item Page URL
#   - Item Type
#   - Item Owner
#   - Sharing Status
#   - Authoritative/Deprecated
#   - Creation Date
#   - Modified Date
#   - File Size
#   - Metadata Summary
#   - Metadata Description
#   - Metadata Tags
#   - Metadata Categories
#   - Metadata Thumbnail
# - A related table based on item id with all the upstream and downstream dependencies for each item (ideally with an indication of whether it is up or downstream)
# - Something that runs quickly enough that can be easily scheduled to run at a defined cadence within ArcGIS Online standard notebooks (so it doesn't use credits)
#   - The script should add new items, update changed items, and delete items that no longer exist from the created hosted feature layer
#   - The script should NOT change fields in the feature layer that I have added to be manually changed and adjusted to track ADA compliance via the separate Survey123/checklist (so no overwriting the whole layer)
# 

# ## The Actual Script
# <hr>
# Enough with the introduction, here's the meat and potatoes of what I'm trying to acheive. If you want to replicate this process in your own organization, you can clone the related tables that I have and adjust them to suit your fancy (obviously make sure to change any field names in the script as necessary)

# ### Prolog
# Connect to your gis, import libraries, etc...

# In[146]:


from arcgis.gis import GIS
from arcgis.features import FeatureLayerCollection
import arcgis.apps.itemgraph
import pandas as pd
from arcgis.features import FeatureLayer

import warnings
from urllib3.exceptions import InsecureRequestWarning
warnings.simplefilter("ignore", InsecureRequestWarning)

gis = GIS("home")


# In[147]:


all_items = gis.content.search(query="*", max_items=10000)

print(f"Total items found: {len(all_items)}")


# ### Create and Export the itemgraph
# You can learn all about itemgraphs in this [blog post](https://www.esri.com/arcgis-blog/products/api-python/announcements/whats-new-in-arcgis-api-for-python-2-4-1-april-2025) -- they do a way better job of explaining than I ever could. I'm sure there's a million ways you could go about reviewing data and then publishing, but I've chosen to export the itemgraph to an excel spreadsheet so I could take a look at things if I want, then I update the layer using that (instead of going directly from itemgraph to hosted table, which admittedly made my head explode when I was first trying it). 

# In[3]:


# Create itemgraph

dependence_graph= arcgis.apps.itemgraph.create_dependency_graph(gis=gis,item_list=all_items,outside_org=False,include_reverse=True)


# To be honest, I'm not 100% sure what itemgraphs look like, all I know is that I can get each of the content items details from the "nodes" and then the dependencies from the "edges". I've made sure to capture the various fields that I want into the df. 

# In[148]:


# Extract Nodes (Items) -- this is itemgraph lingo, gemini helped me out here. 

nodes_data = []
for node_id in dependence_graph.nodes:
    node = dependence_graph.get_node(node_id)
    nodes_data.append({
        
        # Make sure that the column names match the field names in the layer
        "item_id": node.item.id,
        "item_title": node.item.title,
        "item_type": node.item.type,
        "item_owner": node.item.owner,
        "item_url": node.item.homepage,
        "item_sharing": node.item.access,
        "item_status": node.item.content_status,
        # because everyone knows that dates are a pain and can't be simple
        "item_date_created": pd.to_datetime(node.item.created, unit='ms').date(),
        "item_date_modified": pd.to_datetime(node.item.modified, unit='ms').date(),
        # I just want to know if it has these, doesn't need to return everything
        "has_metadata_description": str(bool(node.item.description and node.item.description.strip())).upper(),
        "has_metadata_summary": str(bool(node.item.snippet and node.item.snippet.strip())).upper(),
        "has_metadata_tags": str(bool(node.item.tags and len(node.item.tags) > 0)).upper(),
        "has_metadata_categories": str(bool(node.item.categories and len(node.item.categories) > 0)).upper(),
        "has_thumbnail": str(bool(node.item.thumbnail)).upper(),
        "file_size": node.item.size 
        
    })


# In[149]:


# Extract Edges (Relationships/Dependencies) -- this is itemgraph lingo, gemini helped me out here

edges_data = []
for edge in dependence_graph.edges:
    source_id, target_id = edge
    source_node = dependence_graph.get_node(source_id)
    target_node = dependence_graph.get_node(target_id)
    
    edges_data.append({
        
        # Adjust which fields you want captured as needed
        "origin_title": source_node.item.title,
        "origin_id": source_id,
        "relationship": "Depends On",
        "dependent_title": target_node.item.title,
        "dependent_id": target_id,
        "dependent_owner": target_node.item.owner,
        "dependent_type": target_node.item.type,
        "dependent_sharing": target_node.item.access,
        "dependent_status": target_node.item.content_status,
        "dependent_date_created": pd.to_datetime(target_node.item.created, unit='ms').date(),
        "dependent_date_modified": pd.to_datetime(target_node.item.modified, unit='ms').date(),
        "dependent_item_page_url": target_node.item.homepage
    })


# In[150]:


# #Add upsteam edges

# for edge in dependence_graph.edges:
#     source_id, target_id = edge
#     source_node = dependence_graph.get_node(source_id)
#     target_node = dependence_graph.get_node(target_id)
    
#     edges_data.append({
        
#         # swap target and source to see the upstream dependencies in the related table
#         "origin_title": target_node.item.title,
#         "origin_id": target_id,
#         "relationship": "Is Used In",
#         "dependent_title": source_node.item.title,
#         "dependent_id": source_id,
#         "dependent_owner": source_node.item.owner,
#         "dependent_type": source_node.item.type,
#         "dependent_sharing": source_node.item.access,
#         "dependent_status": source_node.item.content_status,
#         "dependent_date_created": pd.to_datetime(source_node.item.created, unit='ms').date(),
#         "dependent_date_modified": pd.to_datetime(source_node.item.modified, unit='ms').date(),
#         "dependent_item_page_url": source_node.item.homepage})


# In[151]:


# Append View Layer relationships
# We iterate through the nodes to find Feature Layers and check for their views
for node_id in dependence_graph.nodes:
    node = dependence_graph.get_node(node_id)
    item = node.item
    
    # We only look for views originating FROM Hosted Feature Layers
    if item.type == "Feature Service":
        # 'service2ServiceLayerView' is the specific relationship for views
        views = item.related_items(rel_type="Service2Service", direction="forward")
        
        for view_item in views:
            edges_data.append({
                "origin_title": item.title,
                "origin_id": item.id,
                "relationship": "Host to View", # Distinguish this relationship
                "dependent_title": view_item.title,
                "dependent_id": view_item.id,
                "dependent_owner": view_item.owner,
                "dependent_type": view_item.type,
                "dependent_sharing": view_item.access,
                "dependent_status": view_item.content_status,
                "dependent_date_created": pd.to_datetime(view_item.created, unit='ms').date(),
                "dependent_date_modified": pd.to_datetime(view_item.modified, unit='ms').date(),
                "dependent_item_page_url": view_item.homepage
            })


# You could probably skip downloading and then subsequently reading the excel file, but that's just not how I roll. 

# In[152]:


# Create DataFrames and Export to Excel
df_nodes = pd.DataFrame(nodes_data)
df_edges = pd.DataFrame(edges_data)

# Obviously change the file name if you want, but this file name is also called back below for updating the hosted tables
with pd.ExcelWriter("ArcGIS_ItemGraph_Report.xlsx") as writer:
    df_nodes.to_excel(writer, sheet_name="Items_Nodes", index=False)
    df_edges.to_excel(writer, sheet_name="Dependencies_Edges", index=False)

print("Excel file created successfully.")


# ### Update the Content Hosted Table
# This is where we want to make sure we are only updating the fields that we want, and adding or deleting items as necessary. 

# In[127]:


# Configuration
EXCEL_PATH = "ArcGIS_ItemGraph_Report.xlsx"
UNIQUE_ID_FIELD = "item_id"  # This must match the field name in both Excel and ArcGIS

# Make sure you grab the service URL for the content sub table (and not the dependency sub table)
flayer = FeatureLayer("https://services6.arcgis.com/KaHXE9OkiB9e63uE/arcgis/rest/services/AGOL_Dependencies_Monitoring_Copy/FeatureServer/1")
print(flayer)


# Cleaning up the tables to give us a better chance at success...

# In[128]:


# Load Data
df_excel = pd.read_excel(EXCEL_PATH, sheet_name="Items_Nodes")

# Ensure the Unique ID is treated as a string to avoid matching errors
df_excel[UNIQUE_ID_FIELD] = df_excel[UNIQUE_ID_FIELD].astype(str)

# Get Valid Layer Fields (excluding system-managed fields)
# This prevents errors caused by trying to update protected fields
ignored_fields=['has_dependencies','dependencies_count','action_notes','upstream_count','review_status','ADA_Status','WAVE_reviewed','interactive_content_alt_text','widget_info','ReviewerName']
layer_fields = [f['name'] for f in flayer.properties.fields 
                if f['editable'] and f['type'] not in ['esriFieldTypeOID', 'esriFieldTypeGlobalID']
               and f['name'] not in ignored_fields]
print(f"Editable fields in layer: {layer_fields}")

# Clean Excel: Keep only columns that exist in the Layer
# This ensures we don't send "extra" columns that will cause the API to fail
cols_to_keep = [c for c in df_excel.columns if c in layer_fields or c == UNIQUE_ID_FIELD]
print(cols_to_keep)
df_sync = df_excel[cols_to_keep].copy()

# Convert NaN to None (ArcGIS handles None as Null, but hates NaN)
df_sync = df_sync.where(pd.notnull(df_sync), None)
#print(df_sync)


# In[129]:


# Get Existing Data for Matching
existing_fset = flayer.query(where="1=1", out_fields="*")
ids_in_layer = {str(f.attributes[UNIQUE_ID_FIELD]): f for f in existing_fset.features}

adds = []
updates = []


# Adding, Updating and Deleting

# In[130]:


# Process Records
for _, row in df_sync.iterrows():
    attributes = row.to_dict()
    current_id = str(attributes[UNIQUE_ID_FIELD])
    
    if current_id in ids_in_layer:
        # UPDATE
        target_feature = ids_in_layer[current_id]
        target_feature.attributes.update(attributes)
        updates.append(target_feature)
    else:
        # ADD
        adds.append({"attributes": attributes})


# In[131]:


# Identify Deletes (Feature in Layer but not in Excel)
excel_ids = set(df_sync[UNIQUE_ID_FIELD].astype(str).tolist())
oid_field = flayer.properties.objectIdField
deletes = [str(f.attributes[oid_field]) for f in existing_fset.features 
           if str(f.attributes[UNIQUE_ID_FIELD]) not in excel_ids]


# In[132]:


# Push Edits
print(f"Syncing: {len(adds)} adds, {len(updates)} updates, {len(deletes)} deletes...")

if adds or updates or deletes:
    # Use rollback_on_failure=True to ensure data integrity
    response = flayer.edit_features(
        adds=adds, 
        updates=updates, 
        deletes=",".join(deletes),
        rollback_on_failure=True
    )
    #print("Response summary:", response)
else:
    print("No changes needed.")


# ### Update the Dependency Related Table
# This is a bit easier because we can just overwrite the whole table with what the itemgraph produces

# In[153]:


# Config
Dependencies_SHEET_NAME = "Dependencies_Edges"
d_flayer = FeatureLayer("https://services6.arcgis.com/KaHXE9OkiB9e63uE/arcgis/rest/services/AGOL_Dependencies_Monitoring_Copy/FeatureServer/0")

# Load the specific sheet
df_new = pd.read_excel(EXCEL_PATH, sheet_name=Dependencies_SHEET_NAME)
#print(df_new)


# In[154]:


# Clean the data (Handle NaNs and field matching)
# Get editable field names from the target layer to ensure compatibility
layer_fields = {f['name']: f['type'] for f in d_flayer.properties.fields if f['editable']}
print(f"Target Layer expects these fields: {list(layer_fields.keys())}")


# In[155]:


# Filter Excel to only include columns that exist in the target layer
cols_to_use = [c for c in df_new.columns if c in layer_fields]
print(cols_to_use)
df_new_sync = df_new[cols_to_use].copy()
df_new_sync = df_new_sync.where(pd.notnull(df_new_sync), None) # Convert NaN to None
print(df_new_sync)



# In[156]:


# Convert DataFrame to List of Features
new_features = [{"attributes": row.to_dict()} for _, row in df_new_sync.iterrows()]




# In[157]:


if not new_features:
    print("Error: No data found in Excel sheet to upload!")
else:
    # 4. Truncate
    print(f"Clearing existing data...")
    d_flayer.delete_features(where="1=1")
    print(d_flayer)

    # 5. Add with Error Reporting
    print(f"Attempting to add {len(new_features)} features...")
    response = d_flayer.edit_features(adds=new_features, rollback_on_failure=False)

    # 6. Check results
    add_results = response.get('addResults', [])
    successes = [res for res in add_results if res['success']]
    failures = [res for res in add_results if not res['success']]

    print(f"Successfully added: {len(successes)}")
    print(f"Failed to add: {len(failures)}")

    if failures:
        print("\n--- FIRST FAILURE ERROR DETAILS ---")
        print(failures[0]['error'])
        # Common errors: "Field 'X' is not nullable", "Value is too long", "Wrong data type"


# In[ ]:




