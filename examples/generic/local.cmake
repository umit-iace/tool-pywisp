# LOCAL COPY DEPENDENCY MANAGEMENT
## in case you already have a copy of a dependency and
## don't want to download it for every project separately,
## define a variable named
## FETCHCONTENT_SOURCE_DIR_<ucName>
## that points to the PATH of the dependency.
## <ucName> is the UPPER_CASED name of the dependency
#  WARNING:
## Take note the CMAKE will NOT look at this path to
## make sure the dependency is available if you use this.

# GIT
## make sure that your local updates of this file don't
## get pushed to other people, as their setup differs
## from yours.
## To achieve this, just run the following git command
## in the folder that contains this file
# $ git update-index --skip-worktree local.cmake

# EXAMPLES
## uncomment the following line if you have a local copy
## of TOOL-LIBS and don't want to download it for every
## project separately. Make sure the PATH points to it.
#  WARNING:
## FetchContent will NOT update TOOL-LIBS if you do this.
## It will NOT make sure the correct TAG is checked out.
#set(FETCHCONTENT_SOURCE_DIR_TOOL-LIBS $ENV{HOME}/git/tool-libs/)
