# run on 2025-11-07 under macos:
# % uname -a
# > Darwin Anonymouss-MacBook-Air.local 24.6.0 Darwin Kernel Version 24.6.0: Mon Jul 14 11:30:40 PDT 2025; root:xnu-11417.140.69~1/RELEASE_ARM64_T8132 arm64
# % system_profiler SPHardwareDataType | grep "Model"
# >      Model Name: MacBook Air
# >      Model Identifier: Mac16,12
# >      Model Number: Z1GS000RCLL/A

# with 'govon' conda env activated (openjdk version 21.0.6 build h514c7bf_0)

# rdfexport drawio plugin unreleased, commit hash:
# https://github.com/gbad-project/drawio/tree/0161dbcfaf562d2e68697971ec0cd558a853343a

# % shasum -a 256 *
# > f0cdf09dfd7fc5c7a51852710dd0135704f36ceaa50a8f426c8671fc59032ba3  general_add_no_rr_2025-11-07_base_added.rml.ttl
# > 265cf6aa56c8d9bc1751f146d9e36ceaad1ba40de087df2ca42deebe0fa2a507  general_add_no_rr_2025-11-07.drawio
# > 2e9e9befecda006275d4cd478c746b7e1699407b200941b0ca3266a4e46d4034  general_add_no_rr_2025-11-07.ttl
# > d7ce320c2302a1441fe1b15c6b15c310239ba434fe6c8917f8020bd4a19163dd  general_add_output.ttl
# > 9e6a9ce1a2674b8e07ca2d6d471183621529c4eac181cbd3ea241f2ff8cf6117  general_add_pipeline_preprocessed_2025-11-07.csv
# > 28964ae13a4e348ecdd96a77af0fbcf3e08c7acfedafce18dbe37a4b139f1078  general_auth_output.ttl
# > 6f4cea3759ab7e59bff7f937fa83fe586894b942109a8a509fe1315539fc1a09  general_authority_no_rr_2025-11-07_base_added.rml.ttl
# > b99b791ba047cefba961a7f57369601ac7d93facf5d063e51af063a2ba811b1e  general_authority_no_rr_2025-11-07.drawio
# > 489c17cfa40eeb3de045bd4a0c0b57eef579c3f14bafa1b653bd71ed332abb8d  general_authority_pipeline_preprocessed_2025-11-07.csv
# > 925f83c4d029f56b18b81427484163f634edede6e0d620d572e04a9014de922f  rmlmapper-7.0.0-r374-all.jar
# > dc65739ce5afc0c4b13d5d8e9ca13411dfd3a6268c0d7996607590e7460ad680  rmlmapper-8.0.0-r378-all.jar

# https://github.com/RMLio/rmlmapper-java/releases/tag/v8.0.0
java -jar rmlmapper-8.0.0-r378-all.jar -s turtle -m general_add_no_rr_2025-11-07.rml.ttl -o general_add_output.ttl
# optionally with `-b https://data.archives.gov.on.test.gbad.ca` if @base is not hardcoded into rml

java -jar rmlmapper-8.0.0-r378-all.jar -s turtle -m general_authority_no_rr_2025-11-07.rml.ttl -o general_auth_output.ttl
# optionally with `-b https://data.archives.gov.on.test.gbad.ca` if @base is not hardcoded into rml

# https://github.com/RMLio/rmlmapper-java/releases/tag/v7.0.0
# `rmlmapper-7.0.0-r374-all.jar` should work also
