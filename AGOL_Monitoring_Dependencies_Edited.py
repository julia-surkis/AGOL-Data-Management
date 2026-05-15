#!/usr/bin/env python
# coding: utf-8

# # ArcGIS Online: Dependencies Dashboard

# It's the $64k questions when you're looking at an AGOL org on its way to becomming a junk drawer:<br>
# 
# ### _**<span style="color: orange;">"If I delete this ( service / map ), how many ( maps / apps ) am I going to break?"</span>**_
# 
# I suspect Esri is close to rolling out a GUI to assist in this perennial question / admin plight. In fact I figured there is no better way to ensure that this Esri tool is rolled out in the next update of AGOL than to build one myself, if for no other reason than to have a stop-gap (and to put it in my GIS portfolio).
# 
# Various iterations of tools to report dependencies already exist, floating around the Esri community boards etc. My take on the problem is a little bit different than some of the versions I investigated:
# 
# * **It is intended to be run as an ArcGIS Notebook connected to AGOL (either from ArcGIS Pro or within AGOL itself).**
#     * I don't have the capacity to test in Enterprise, but I expect it would work there with no more than some minor alterations (if any).
# * **I have tried to optimize performance in a number of ways over some toolbox versions I have seen** (some of which were reported to take a significant amount of time to run in AGOL).
# 
# * **Rather than outputing a CSV or Excel, this tool writes its output to a pair of hosted tables within AGOL, which are connected to a Dashboard.** The Dashboard allows for interactive investigation of items and their dependencies, and includes HTML links to dependent Item pages, etc.
# 
# ### Related Item Links
# 
# * [**ArcGIS Hosted Tables Template**](https://arcgis.com/home/item.html?id=518d7acfdb0d4c7e8e967c46fd1e6edf) A pair of (empty) hosted tables with an identical schema to the tables whose data are displayed in the dashboard. These are free for anyone to grab if they are looking to implement this script and workflow.
# 
# * [**ArcGIS Dashboard**](https://arcgis.com/apps/dashboards/37d7586b663c4f86bb6bb3c87e316ba6) The Dashboard currently airing my AGOL dirty laundry / serving as an example of how the script + hosted tables + Dashboard work together for Dependencies monitoring.
# 
# ### How it works
# 
# The high-level functionality of this script is similar to other dependencies tools out there: It iterates over all items in the current AGOL org and searches the item data (i.e. JSON) for item IDs. For a given item, IDs for other items found within that item's own JSON are dependencies (I have been calling them downstream dependencies, i.e. feature layers are downstream dependencies of a web map). Also for a given item, that item's ID found in *other item's* JSON are also dependencies (upstream dependencies, e.g. apps that are consuming a web map are upstream dependencies of that web map).
# 
# Note that this tool does *not* make use of the [ItemDependency object](https://developers.arcgis.com/python/latest/api-reference/arcgis.gis.toc.html#arcgis.gis.ItemDependency) found in the [ArcGIS API for Python reference documentation](https://developers.arcgis.com/python/latest/api-reference/). I would have liked to do that, and I tried to do that, but that functionality seems just not to function at the moment ([as others have noted](https://community.esri.com/t5/arcgis-api-for-python-questions/dependencies-arcgis-gis-itemdependency-to/m-p/1652176)).
# 
# This script also does *not* use the [get_dependencies method](https://developers.arcgis.com/python/latest/api-reference/arcgis.gis.toc.html#arcgis.gis.Item.get_dependencies), also in the API reference. This method at least returns something, but it only returns items found *within that items own JSON*, or downstream items. I.e., it will return all the feature layers found in a given map, but not which apps are consuming that map, and not which maps are consuming a given feature service, etc. (the latter, I would argue, is the whole point of a dependencies tool).
# 
# __Update Oct 13 2025__
# 
# Esri literally just put out (Oct 1st) a [sweet little script for finding Dependencies](https://support.esri.com/en-us/knowledge-base/how-to-find-dependencies-in-portal-for-arcgis-using-arc-000021183) in Portal for ArcGIS; check it out if that's where you're working. Doesn't help those of us working in ArcGIS Online because the methods used, dependent_upon and dependent_to, only work in Enterprise, not AGOL.
# 
# ### Efficience & Performance
# 
# I've tried to optimize this tool for performance in AGOL in a couple of ways:
# 
# * **Iterate all JSON object once, build dictionary of ID: IDs.** Instead of iterating over *all* of the JSON in *all* of the contents of AGOL *for every Item ID*, I start out the script by iterating all JSON *once*, and building a Python dictionary with what I find, where the Item ID of the item I'm searching is the key, and a list (okay technically a set) of the Item IDs found *within that item's JSON* is the value. Once this dictionary is built, I can simply search that dictionary when iterating over all item IDs, rather than repeatedly searching whole JSON objects.
# 
# * **While building ID: IDs dictionary, recursively walk JSON.** When building the dictionary above, instead of using json.dumps and searching for an item ID as a substring of the whole JSON string, I recursively walk the JSON, which ChatGPT tells me is the more efficient approach. Note that I have not done rigrous comparison testing! Within my Personal Use Org, currently housing about 230 items, this script runs in about 12 minutes.

# <hr>
# 
# ### DISCLAIMER
# 
# The combination of script + tables + Dashboard should find the _vast majority_ of item dependencies in your org, but it _may not find them all_. I.e., when cleaning up your AGOL or Portal: use common sense, be diligent, test, and remember that the recycle bin is your friend.
# 
# <hr>

# ## Prolog(in): Vars, Imports & Connect to AGOL
# <hr>
# 
# #### __If you'd like to use this script and workflow for your org:__ you need to do a few things:
# * grab a copy of the hosted tables template and re-publish to your org
# * grab a copy of the Dashboard template and hook it up to your hosted tables
# * grab a copy of this script, plug it into your editor of choice (Notebook in Pro or AGOL, VS Code, whatever)
# 
# If you take care to maintain the ids of the two tables when publishing them, the ONLY thing you should have to change in this script is the ID below, which is the ID of those tables. Everything else, in theory, should _just work_. Now we all know how it goes with things that should, in theory, _just work_, but hey my markdown needs a baseline of some kind.

# In[1]:


# If you appropriate for your own nefarious uses, 
# replace this ID with the ID to your own re-published tables
dashboard_tables_id = "290d97c83f774d95941dcbab13b52e85"


# #### Switch to turn on checking for Dependencies by URL
# 
# Switch is off if set to False; on if set to True. This will capture a fraction of additional Dependencies (~5% of all Dependencies were caught with this switch on in my Personal Use AGOL), but the script will take about 2X as long to run. See [more in-depth explanation](#check-urls-found-in-json-data-and-retrieve-item-id-for-feature-services-if-possible) of the function used by the switch a couple of cells down.

# In[2]:


check_urls = True


# The warnings import and additional shenanigans are to suppress (not legit) [warnings](https://github.com/Esri/arcgis-python-api/issues/2164) generated when arg for max_items parameter for gis.content.get is >200.

# In[3]:


from arcgis.gis import GIS
from arcgis.features import FeatureLayerCollection
import arcgis.apps.itemgraph

import warnings
from urllib3.exceptions import InsecureRequestWarning
warnings.simplefilter("ignore", InsecureRequestWarning)

gis = GIS("home")


# ## Part I: Functions: Process Dependencies
# <hr>

# #### Check URLs found in JSON Data and retrieve Item ID for Feature Services if possible
# 
# This function is called from within the walk_json function below, _only if_ "check_urls" switch is set to "True" at the top of the notebook.
# 
# References can exist in an Item's JSON data in the form of a rest endpoint URL _only_ (i.e. without the associated Item ID referenced explicitely). These items would still be dependencies but will not be caught if this function is not called. Dependencies caught in this way will in most casely likely account for a small minority of Dependencies (in my current unkempt Personal Use portal, only 26 of 421 references are found via this function). But turning on the check doubles the run time, which is why I have built in a switch to turn the functionality off, if admins want a quick-and-dirty look at their dependencies situation.
# 
# Dependencies referenced by URL only can turn up in a few ways; custom GP tools may have been built to reference URLs only, for example. Also, once upon a time they could creep into Web Maps, if you opened the map in ArcGIS Pro, swapped out one service URL for another as a source for one of the layers, and then pushed the changes back to AGOL. In older versions of Pro (maybe pre-3.x?), the Item ID reference for that layer would simply be dropped instead of swapped (to be fair, Pro would warn you about it). This no longer happens in Pro, but web maps with missing ID references could still be out there. 
# 
# Note that this function _only_ checks for Feature Service URLs!

# In[4]:


def get_id_from_url(url):

    # We may not find an ID to return;
    # Declar var to return as false initially
    flc_id = False

    # We may find either a feature layer URL (...FeatureServer/0)
    # or we may find a feature layer collection URL (...FeatureServer)
    # Split and see whether split URL ends with a numeric
    check = url.rsplit("/", maxsplit=1)
    if check[1].isnumeric():
        url = check[0]

    # I only want to treat Feature Services (because Map Services are just ugh)
    if url.endswith("FeatureServer"):

        # I encountered vague and rude errors while attempting
        # to retrieve feature layer collection, so wrapping in try
        try:
            # Get the Feature Layer Collection object and from that the ID
            flc_obj = FeatureLayerCollection(url)
            flc_id = flc_obj.properties.serviceItemId

        # ...and print a polite message in response to any rudeness
        except Exception as e:
            print(f"""
                Could not retrieve Item ID for the following URL:\n {url}
                May be outside org?
                The following error was returned:\n {e}
                Its ID will not be added as a dependency ID; skipping!
                """)

    return flc_id


# #### Walk the (JSON) data of a single item in the Org
# 
# This function is called once per item for ever item in the ArcGIS Online Org. It is used to build a set of all Item IDs found within the JSON of the Item data (get_data method on the Item object) passed into the function.
# 
# Instead of using json.dumps or something similar to convert the JSON object to one big string, this function recursively walks the JSON structure looking for values that match the format of an AGOL Item ID (32 alphanumeric characters).
# 
# Although there is a possibility here of adding non-item IDs to the set (e.g., folder IDs are also 32-char alnum), it doesn't matter because they will simply never match an Item ID when the dictionary is being searched, and I suspect the cost of the logic to remove them is as much or more than the cost of iterating over some non-ID values.

# In[5]:


def walk_json(item_data):
    
    # Set instead of List so I don't have to worry about removing duplicate IDs down the road
    items_set = set()

    # If this level of the JSON structure is a dictionary, 
    # call the function again and look at all the values
    if isinstance(item_data, dict):
        for value in item_data.values():
            items_set.update(walk_json(value))

    # If this level of the JSON structure is a list, 
    # call the function again and look at all elements of the list
    elif isinstance(item_data, list):
        for value in item_data:
            items_set.update(walk_json(value))

    # If (finally) this level of the JSON structure is a string,
    # if it matches the format of an Item ID (32-char alphanumeric),
    # add to my set of IDs for the current Item ID
    elif isinstance(item_data, str):

        if len(item_data) == 32 and item_data.isalnum():
            items_set.add(item_data)
            print("added ", item_data)

        if check_urls:
            if "/arcgis/rest/services/" in item_data:
                id_from_url = get_id_from_url(item_data)
                if id_from_url:
                    items_set.add(id_from_url)
                    print("added ",id_from_url)

    return items_set


# #### Create the ID dictionary and add downstream dependencies
# This function calls the above function iteratively for all Items in the org to build a dictionary of ID: Dependency IDs for the whole org. Note that this function only adds the downstream dependencies to the dictionary; upstream dependencies are added by the get_dependencies_dict function below.

# In[6]:


def get_downstream_dict():

    downstream_dict = {}

    for item in all_items:

        print(item)

        # For each item, call the function to walk the item JSON,
        # passing in the item's own data (get_data returns the JSON)
        downstream_set = walk_json(item.get_data())

        # Add the key/value pair (Item ID / set of Dependent IDs) to the dictionary
        downstream_dict[item.id] = downstream_set
        print(item, " Done")

    print("Downstream dictionary assembled successfully")

    return downstream_dict


# #### (TRYING WITHOUT) Add upstream dependencies to downstream dependencies and complete the dictionary
# Getting an item's downstream dependencies is relatively easy because it only involves searching *within the item's own JSON*. I.e., the JSON of a web map will, of course, contain the Item IDs of all the layers included in the map (downstream dependencies).
# 
# Adding upstream dependencies involves additional logical steps because it involves searching the JSON of *all other items*. I.e., the Item ID of a web map will be found in the JSON of all the apps or dashboards that consume it. This function completes the Dependencies dictionary by adding upstream dependencies to the downstream dependencies.

# In[ ]:


# def get_dependencies_dict():

#     # First, iterate through the keys (IDs) of the downstream dictionary
#     for key in downstream_dict:
        
#         # For each key, iterate through the same dictionary again
#         for k, v in downstream_dict.items():

#             # For each value (list of IDs in that item JSON),
#             # check if the ky from the outer loop is among the values
#             if key in v:

#                 # If it is (e.g., if I find the ID of a web map in the first loop)
#                 # in the list of IDs from a Dashboard in the outer loop),
#                 # I've found a dependency; add the inner loop ID to the value (set) at the outer loop ID
#                 downstream_dict[key].add(k)

#     # The resulting dictionary will contain values that are empty sets
#     # (e.g. items with no dependencies found). No point in including these
#     # in the lookup process later, so re-create the dict with only populated sets
#     dependencies_dict = {k:v for k, v in downstream_dict.items() if v}

#     print("Dependencies dictionary assembled successfully")

#     return dependencies_dict


# #### (TRYING WITHOUT) Get the Dependencies (Item objects) for a Given item
# Once the Dependencies dictionary has been built with the above functions, the function below retrieves the actual Item objects for all dependencies for a given item (the Item object is needed to supply properties used to populate the Dashboard tables). The ID for the current item is passed in; the dependencies dictionary is used to look up the dependent item IDs.

# In[ ]:


# def get_dependencies(item_id):

#     # Initialize empty list to hold item objects
#     items_list = []

#     # Only items that were found to have dependencies
#     # are in the lookup dictionary; check first
#     if item_id in dependencies_dict:

#         # Get the list of dependency IDs from the dict
#         ids_list = dependencies_dict[item_id]
        
#         # Iterate through dependency IDs
#         for i in ids_list:

#             # I received permissions errors for an item or two;
#             # mititage problems with that by skipping here
#             try:
#                 item = gis.content.get(i)

#                 # gis.content.get above will return None if no item
#                 # matches that ID (e.g., if the ID is for a folder); check first
#                 if item:

#                     # If the item object is found, append to list of items
#                     items_list.append(item)

#             # Print message for naughty IDs
#             except Exception as e:
#                 print(f"""
#                     Item ID {i} wasn't retrieved; may be outside org?"
#                     The following error was returned:\n {e}
#                     Skipping!
#                 """)

#     return items_list


# ## Part II: Functions: Table Attribute Helpers
# Instead of simply writing raw item properties, these helper functions massage those properties a bit to make the Dashboard tables more intuitive for users.
# <hr>
# 
# This function creates a string that is an html link to an actual item (not the item page), depending on the item type. For services, it returns and HTML link string wrapping the .url Item object property. For web map, it returns an HTML link string wrapping a concatenation of the default web map viewer URL and Item ID. For most apps, it returns an HTML link string wrapping the URL to the app itself (also the Item .url property).
# 
# Links will only work for users who have permission to view the item. For any but publicly shared apps / web maps / services, users who are not already logged in will be asked to do so.

# In[7]:


def get_item_url(item):

    # Services: creates an HTML link string to the service REST endpoint URL (.url property of the Item)
    if item.type in ["Vector Tile Service", "Feature Service", "Map Service", "Image Service"]:
        return f'<a target="_blank" href="{item.url}">View Service</a>'
    
    # Web maps: creates an HTML link to open the map in Map Viewer app
    elif item.type == "Web Map":
        return f'<a target="_blank" href="https://arcgis.com/apps/mapviewer/index.html?webmap={item.id}">View Map</a>'
    
    # Web apps: creates an HTML link string to the app URL itself (.url property of the Item)
    elif item.type in ["Hub Site Application", "StoryMap", "Web Experience", "Web Experience Template", "Dashboard", "Hub Page"]:
        return f'<a target="_blank" href="{item.url}">View App</a>'
    
    else: return "Not applicable"


# This function creates an HTML string link to the Item ID page.

# In[8]:


def get_item_page_url(item_id):
    return f'<a target="_blank" href="https://arcgis.com/home/item.html?id={item_id}">View Item Page</a>'


# This function is used to populate the "Item Sharing" field of the Dashboard attribute tables. It parses the dictionary returned by the shared_with property off the SharingManager object (which is itself returned by the "sharing" property off the Item) and returns user-friendly categories (without specific Group names) for the Dashboard.

# In[9]:


def get_sharing(sharing):

    # "groups" key returns list of groups; I only care whether it's empty or not
    groups = len(sharing.shared_with["groups"])
    
    # "Level" key of dict returns an enum instance - fun!
    # Just get the value (one of 3: PRIVATE, ORGANIZATION or EVERYONE)
    level = sharing.shared_with["level"].value

    # If there are groups, return some custom strings based on level
    if groups:
        if level == "PRIVATE":
            return "Groups only"
        else: return f"Groups & {level.title()}"

    # Otherwise just return the level (in title case)
    else:
        return level.title()


# This function populates the "Status" field (whether an item is marked "Authoritative", "Depricated" or not marked as either). Status is a property off the Item object so I only need to remove the "org_" prefix and convert the value to title case.

# In[10]:


def get_status(status):
    if not status:
        return "None"
    else: return status.lstrip("org_").title()


# ## Part III: Functions: Write Attributes (Items & Dependencies)
# This section consists of only two functions: one writes attributes to the main Item table; the other writes attributes to the Dependencies table.
# <hr>
# 
# #### Build Item table rows
# 
# This function builds a dictionary of rows to be written to the Items Dashboard table in the format of field name: attribute value, which is the row format required for updating the hosted table via the edit_features method. Two fields (arguably redundant but user-friendly) focus on whether the given item has dependencies.

# In[11]:


def add_attributes(item, dependencies):
    
    # Empty dictionary to hold key/vals for this row
    items_dict = {}

    # Value assignments that do not call a function simply reference Item properties
    items_dict["item_id"] = item.id
    items_dict["item_title"] = item.title
    items_dict["item_owner"] = item.owner
    items_dict["item_type"] = item.type

    # Call to heper function above to return Item page URL
    items_dict["item_page_url"] = get_item_page_url(item.id)

    # Call to helper function above to get type-dependent Item URL
    items_dict["item_url"] = get_item_url(item)

    # Call to helper function above to parse sharing property
    items_dict["item_sharing"] = get_sharing(item.sharing)

    # Call to helper function above to get Item status
    items_dict["item_status"] = get_status(item.content_status)

    items_dict["item_date_created"] = item.created
    items_dict["item_date_modified"] = item.modified

    # Populate 2 Dependency-related fields
    if not dependencies:
        items_dict["has_dependencies"] = "No"
        items_dict["dependencies_count"] = 0

    else:
        items_dict["has_dependencies"] = "Yes"
        items_dict["dependencies_count"] = len(dependencies)

    return items_dict


# #### Build Dependencies table rows
# 
# Uncomfortably similar to the above function, but this one writes rows for items in the Dependency table rather than the Item table. Field names reflect those in the Dependency table and include both an Origin ID & Title and Dependency ID & Title.

# In[12]:


def add_dependency_attributes(item, dependency):
    
    dependency_dict = {}

    # Value assignments that do not call a function simply return item properties
    dependency_dict["origin_id"] = item.id
    dependency_dict["origin_title"] = item.title
    dependency_dict["dependent_id"] = dependency.id
    dependency_dict["dependent_title"] = dependency.title
    dependency_dict["dependent_owner"] = item.owner
    dependency_dict["dependent_type"] = dependency.type

    # Call to helper function to get the Item Page URL
    dependency_dict["dependent_item_page_url"] = get_item_page_url(dependency.id)

    # Call to helper function to get the item type dependent URL
    dependency_dict["dependent_item_url"] = get_item_url(dependency)

    # Call to parse the sharing property and return user-friendly values
    dependency_dict["dependent_sharing"] = get_sharing(item.sharing)

    # Call to get the user-friendly status
    dependency_dict["dependent_status"] = get_status(item.content_status)

    dependency_dict["dependent_date_created"] = item.created
    dependency_dict["dependent_date_modified"] = item.modified

    return dependency_dict


# ## Part 4: Actually Run Stuff: Get All AGOL Items
# <hr>
# 
# Get all items from current AGOL. (Make sure you're not accidentally connected to the wrong AGOL org while you're taking a MOOC as I have been 🤣)

# In[13]:


all_items = gis.content.search(query="*", max_items=10000)

print(f"Total portal items found: {len(all_items)}")


# #### Build the Dependencies look-up Dictionary
# 
# Calls to two functions to assemble the full dependencies dictionary, which has as keys an item ID and as values a list (technically a set) of IDs that are either upstream or downstream dependencies of the key item. The first call assembles the pre-dictionary but the value (set) includes only downstream dependencies, i.e. item IDs that are found within the key item's own data JSON. The 2nd call expands on the first dictionary to include upstream dependencies, e.g. dependencies where the key item ID is found within _other_ items' JSON.
# 
# I did not see a need to differentiate (e.g. within the hosted table rows) which are upstream and which are downstream dependencies explicitly, since that should be self-evident from the item types (which is included in the hosted tables); i.e. a feature layer is by definition a downstream dependency of a map, etc.

# In[19]:


dependence_graph= arcgis.apps.itemgraph.create_dependency_graph(gis=gis,item_list=all_items,outside_org=False,include_reverse=True)


# In[25]:


import pandas as pd

# 2. Extract Nodes (Items)
nodes_data = []
for node_id in dependence_graph.nodes:
    node = dependence_graph.get_node(node_id)
    nodes_data.append({
        "Item ID": node.item.id,
        "Item Title": node.item.title,
        "Item Type": node.item.type,
        "Item Owner": node.item.owner,
        #"Org ID": node.item.orgid,
        "Item Page Url": node.item.homepage,
        "Item Sharing": node.item.access,
        "Item Status": node.item.content_status,
        "Item Date Created": pd.to_datetime(node.item.created, unit='ms').date(),
        "Item Date Modified": pd.to_datetime(node.item.modified, unit='ms').date(),
        "Has Metadata Description": bool(node.item.description and node.item.description.strip()),
        "Has Metadata Summary": bool(node.item.snippet and node.item.snippet.strip()),
        "Has Metadata Tags": bool(node.item.tags and len(node.item.tags) > 0),
        "Has Metadata Categories": bool(node.item.categories and len(node.item.categories) > 0),
        "Has Thumbnail": bool(node.item.thumbnail),
        "File Size (MB)": node.item.size 
        
    })

# 3. Extract Edges (Relationships)
edges_data = []
for edge in dependence_graph.edges:
    source_id, target_id = edge
    source_node = dependence_graph.get_node(source_id)
    target_node = dependence_graph.get_node(target_id)
    
    edges_data.append({
        "Source Title": source_node.item.title,
        "Source ID": source_id,
        "Relationship": "Depends On",
        "Target Title": target_node.item.title,
        "Target ID": target_id
    })

# 4. Create DataFrames and Export to Excel
df_nodes = pd.DataFrame(nodes_data)
df_edges = pd.DataFrame(edges_data)

with pd.ExcelWriter("ArcGIS_ItemGraph_Report.xlsx") as writer:
    df_nodes.to_excel(writer, sheet_name="Items_Nodes", index=False)
    df_edges.to_excel(writer, sheet_name="Dependencies_Edges", index=False)

print("Excel file created successfully.")


# In[56]:


from arcgis.features import FeatureLayer


# In[64]:


# 1. Configuration
EXCEL_PATH = "ArcGIS_ItemGraph_Report.xlsx"
UNIQUE_ID_FIELD = "item_id"  # This must match the field name in both Excel and ArcGIS



flayer = FeatureLayer("https://services6.arcgis.com/KaHXE9OkiB9e63uE/arcgis/rest/services/AGOL_Dependencies_Monitoring_Copy/FeatureServer/1")# Or use FeatureLayer(LAYER_URL)
print(flayer)


# In[72]:


# 2. Load Data
df_excel = pd.read_excel(EXCEL_PATH, sheet_name="Items_Nodes")
# Ensure the Unique ID is treated as a string to avoid matching errors
df_excel[UNIQUE_ID_FIELD] = df_excel[UNIQUE_ID_FIELD].astype(str)

# 2. Get Valid Layer Fields (excluding system-managed fields)
# This prevents errors caused by trying to update protected fields
layer_fields = [f['name'] for f in flayer.properties.fields 
                if f['editable'] and f['type'] not in ['esriFieldTypeOID', 'esriFieldTypeGlobalID']]
print(f"Editable fields in layer: {layer_fields}")

# 4. Clean Excel: Keep only columns that exist in the Layer
# This ensures we don't send "extra" columns that will cause the API to fail
cols_to_keep = [c for c in df_excel.columns if c in layer_fields or c == UNIQUE_ID_FIELD]
df_sync = df_excel[cols_to_keep].copy()

#Convert NaN to None (ArcGIS handles None as Null, but hates NaN)
df_sync = df_sync.where(pd.notnull(df_sync), None)
print(df_sync)


# In[73]:


# 5. Get Existing Data for Matching
existing_fset = flayer.query(where="1=1", out_fields="*")
ids_in_layer = {str(f.attributes[UNIQUE_ID_FIELD]): f for f in existing_fset.features}

adds = []
updates = []


# In[74]:


# 6. Process Records
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


# In[75]:


# 7. Identify Deletes (Feature in Layer but not in Excel)
excel_ids = set(df_sync[UNIQUE_ID_FIELD].astype(str).tolist())
oid_field = flayer.properties.objectIdField
deletes = [str(f.attributes[oid_field]) for f in existing_fset.features 
           if str(f.attributes[UNIQUE_ID_FIELD]) not in excel_ids]


# In[76]:


# 8. Push Edits
print(f"Syncing: {len(adds)} adds, {len(updates)} updates, {len(deletes)} deletes...")

if adds or updates or deletes:
    # Use rollback_on_failure=True to ensure data integrity
    response = flayer.edit_features(
        adds=adds, 
        updates=updates, 
        deletes=",".join(deletes),
        rollback_on_failure=True
    )
    print("Response summary:", response)
else:
    print("No changes needed.")


# In[66]:


# 3. Get Existing Features from ArcGIS
# We query the layer to get current IDs and geometry
existing_features = flayer.query(where="1=1", out_fields=UNIQUE_ID_FIELD)
existing_fset = existing_features.features
existing_ids = [f.attributes[UNIQUE_ID_FIELD] for f in existing_fset]

adds = []
updates = []
deletes = []



# In[ ]:





# In[67]:


# 4. Identify Adds and Updates
for index, row in df_excel.iterrows():
    # Convert row to dictionary for ArcGIS attributes
    new_attributes = row.to_dict()
    current_id = str(new_attributes[UNIQUE_ID_FIELD])
    
    if current_id in existing_ids:
        # Check if it's an update (Find the matching existing feature)
        existing_feat = next(f for f in existing_fset if f.attributes[UNIQUE_ID_FIELD] == current_id)
        
        # Only update if attributes have actually changed (optional but efficient)
        if existing_feat.attributes != new_attributes:
            print(existing_feat.attributes," IS NOT ",new_attributes)
            existing_feat.attributes.update(new_attributes)
            updates.append(existing_feat)
            print("updated ",existing_feat.attributes[UNIQUE_ID_FIELD])
    else:
        # It's a new feature
        adds.append({"attributes": new_attributes})
        print("added ",current_id)



# In[68]:


# 5. Identify Deletes
# Items in ArcGIS that are NOT in the Excel file
excel_ids = set(df_excel[UNIQUE_ID_FIELD].tolist())
for feat in existing_fset:
    if str(feat.attributes[UNIQUE_ID_FIELD]) not in excel_ids:
        deletes.append(feat.attributes[flayer.properties.objectIdField])
        print("deleted ",feat.attributes[UNIQUE_ID_FIELD])



# In[69]:


# 6. Apply Edits
print(f"Summary: {len(adds)} Adds, {len(updates)} Updates, {len(deletes)} Deletes")

if adds or updates or deletes:
    result = flayer.edit_features(
        adds=adds, 
        updates=updates, 
        deletes=str(deletes).strip('[]') # Pass OIDs as a comma-separated string
    )
    print("Layer successfully synced.")
else:
    print("No changes detected.")


# In[ ]:


-------------------------------------


# In[ ]:


downstream_dict = get_downstream_dict()

# TRYING WITHOUT
#dependencies_dict = get_dependencies_dict()


# In[ ]:


print(downstream_dict)


# ## Part 5: Actually Run Stuff: Get Dependencies, Assemble Data to Write
# <hr>
# 
# After the master dependencies dictionary is assembled above, the main task remaining is to iterate (again) through all items in the org, get their dependencies as actual Item objects by looking them up in the dependencies dictionary, then use the Item objects of both the key Item and its Dependencies (specifically, use the Item object properties) to construct rows (one row per Item) that will be used to write both the Item and Dependencies hosted tables, which power our Dashboard (or Experience Builder app; I haven't decided yet 😂).

# In[ ]:


# The required structure to use the edit_features method to update the hosted tables 
# is a list of dictionaries (each dictionary represents one row in the table / one Item object)
# We first initialize empty lists for both items and dependencies to stuff everything in
items_list = []
dependencies_list = []

for item in all_items:

    # Call to the function that is passed an Item ID, looks it up in the 
    # dependencies dictionary, then uses the dependency IDs it finds in that dict
    # to retrieve the actual dependency Item objects, so we can grab the properties
    dependencies = get_dependencies(item.id)

    # First, construct the rows for the key item itself 
    # (Still need to pass in dependencies because this table includes dependencies count)
    items_dict = add_attributes(item, dependencies)

    # Now, iterate through the dependencies...
    for dependency in dependencies:
        
        # ...and construct the rows for them.
        dependency_dict = add_dependency_attributes(item, dependency)

        # To use the edit_features method to update the hosted tables,
        # Each inner dictionary (the row itself) must be stuffed in an outer dictionary
        # with the key "attributes"; the val is the inner (row) dict
        update_dependencies_dict = {"attributes": dependency_dict}

        # Append our tidy attributes dictionary to our list of features to write
        dependencies_list.append(update_dependencies_dict)

    # Back outside the dependencies loop, stuff key Item row in its own "attributes" dict
    update_items_dict = {"attributes": items_dict}

    # Then stuff it in the list of items; both lists are now structured 
    # in such a way that the edit_features method will happily accepty them
    items_list.append(update_items_dict)

print(f"Number of items to add to items table: {len(items_list)}")
print(f"Number of items to add to dependencies table: {len(dependencies_list)}")


# ## Part 6: Actually Run Stuff: Get the Dashboard Tables and (Over)Write
# <hr>
# 
# #### Get the Dashboard tables
# 
# Very simply provide the Dashboard feature layer collection (consisting of only 2 hosted tables, no features per se) ID, pass to content.get; access tables via indices. If you appropriate the schema of these tables and re-publish yourself to use with this script (which I highly encourage you to do!), you must either ensure that the tables have the same IDs when published (0 and 1), OR you must update the indices below to reflect the IDs your tables were published with.
# 
# Also, obviously, you must update the dashboard_tables_id variable with the Item ID of the tables _you_ have published. Everything else...should just work.

# In[ ]:


dashboard_tables_item = gis.content.get(dashboard_tables_id)

monitoring_table = dashboard_tables_item.tables[0]
dependencies_table = dashboard_tables_item.tables[1]


# #### Finally, write the rows
# 
# For both tables, first wipe out all current rows with truncate, then use edit_features method and pass in our assembled data as adds parameter. This effectively overwrites both tables with the new data.

# In[ ]:


monitoring_table.manager.truncate()
items_update = monitoring_table.edit_features(adds=items_list)
print(f"Items added to monitoring table: {len(items_update['addResults'])}")

dependencies_table.manager.truncate()
dependencies_update = dependencies_table.edit_features(adds=dependencies_list)
print(f"Items added to dependencies table: {len(dependencies_update['addResults'])}")

