"""Functional Data - Collection of methods to manage brain response MRI
scans of subjects in experiments. Contains objects to represent and manipulate
functional data files on local disk.
"""

import datetime
import os
import shutil
import tarfile
import uuid

import datastore


# ------------------------------------------------------------------------------
#
# Constants
#
# ------------------------------------------------------------------------------
""""Names of sub-folders in functional data directories."""
# Unpacked Freesurfer directory
DATA_DIRECTORY = 'data'
# Folder for original upload file
UPLOAD_DIRECTORY = 'upload'

"""Unique type identifier for functional data resources."""
TYPE_FUNCDATA = 'FUNCDATA'


# ------------------------------------------------------------------------------
#
# Database Objects
#
# ------------------------------------------------------------------------------
class FunctionalDataHandle(datastore.DataObjectHandle):
    """Handle to access and manipulate brain responses MRI data object. Each
    object has an unique identifier, the timestamp of it's creation, a list of
    properties, and a reference to the functional data file on disk.

    Functional data may either be generated by fMRI's or as a result of
    predictive model runs.

    Attributes
    ----------
    data_directory : string
        (Absolute) Path to directory containing the uploaded data file
    data_file : string
        (Absolute) Path to uploaded functional data file (identified by file
        suffix mgh/mgz or nii/nii.gz).
    upload_file : string
        (Absolute) Path to uploaded functional data file. By now, this is the
        same file as the data_file.
    """
    def __init__(self, identifier, properties, directory, timestamp=None, is_active=True):
        """Initialize the object handle. The directory references a directory
        on the local disk that contains the functional data archive file.

        Parameters
        ----------
        identifier : string
            Unique object identifier
        properties : Dictionary
            Dictionary of fMRI specific properties
        directory : string
            Directory conatining functional data archive file
        timestamp : datetime, optional
            Time stamp of object creation (UTC).
        is_active : Boolean, optional
            Flag indicating whether the object is active or has been deleted.
        """
        # Initialize super class
        super(FunctionalDataHandle, self).__init__(
            identifier,
            timestamp,
            properties,
            directory,
            is_active=is_active
        )
        self.data_directory = os.path.join(directory, DATA_DIRECTORY)
        # The name of the functional data file is expected to be stored as
        # object property FILENAME.
        self.data_file = os.path.join(
            self.data_directory,
            self.properties[datastore.PROPERTY_FILENAME]
        )

    @property
    def type(self):
        """Override the type method of the base class."""
        return TYPE_FUNCDATA

    @property
    def upload_file(self):
        """(Absolute) Path to uploaded functional data file. By now, this is the
        same file as the data_file. Included for compatibility with earlier
        versions.
        """
        return self.data_file


class FMRIDataHandle(FunctionalDataHandle):
    """Handle to access and manipulate a brain responses MRI data object that is
    associated with an experiment. Extends the functional data handle with a
    reference to the associated experiment.

    Attributes
    ----------
    experiment_id : string
        Unique experiment identifier the fMRI data object is associated with
    """
    def __init__(self, func_data, experiment_id):
        """Initialize the object handle. The directory references a directory
        on the local disk that contains the functional data archive file.

        Parameters
        ----------
        func_data : FunctionalDataHandle
            Handle for functional data object
        experiment_id : string
            Unique experiment identifier the fMRI data object is associated with
        """
        # Initialize super class
        # Initialize super class
        super(FMRIDataHandle, self).__init__(
            func_data.identifier,
            func_data.properties,
            func_data.directory,
            timestamp=func_data.timestamp,
            is_active=func_data.is_active
        )
        self.experiment_id = experiment_id


# ------------------------------------------------------------------------------
#
# Object Store
#
# ------------------------------------------------------------------------------
class DefaultFunctionalDataManager(datastore.DefaultObjectStore):
    """Manager for functional data objects. Implements create_object method that
    creates functional data objects in database from a given data file.

    This is a default implentation that uses MongoDB as storage backend.

    Attributes
    ----------
    directory : string
        Base directory on local disk for functional data files.
    """
    def __init__(self, mongo_collection, base_directory):
        """Initialize the MongoDB collection and base directory where to store
        functional data MRI files.

        Parameters
        ----------
        mongo_collection : Collection
            Collection in MongoDB storing functional data information
        base_directory : string
            Base directory on local disk for anatomy files. Files are stored
            in sub-directories named by the object identifier.
        """
        # The original name of uploaded files is a mandatory and immutable
        # property. This name is used as file name when downloading fMRI
        # data. The file type and mime type do not change either.
        properties = [
            datastore.PROPERTY_FILENAME,
            datastore.PROPERTY_FILESIZE,
            datastore.PROPERTY_MIMETYPE,
            datastore.PROPERTY_FUNCDATAFILE
        ]
        # Initialize the super class
        super(DefaultFunctionalDataManager, self).__init__(
            mongo_collection,
            base_directory,
            properties
        )

    def create_object(self, filename, read_only=False):
        """Create a functional data object for the given file. Expects the file
        to be a valid functional data file. Expects exactly one file that has
        suffix mgh/mgz or nii/nii.gz.

        Parameters
        ----------
        filename : string
            Name of the (uploaded) file
        read_only : boolean, optional
            Optional value for the read-only property

        Returns
        -------
        FunctionalDataHandle
            Handle for created functional data object in database
        """
        # Get the file name, i.e., last component of the given absolute path
        prop_name = os.path.basename(os.path.normpath(filename))
        # Ensure that the uploaded file has a valid suffix. Currently no tests
        # are performed to ensure that the file actually conatains any data.
        if prop_name.endswith('.nii.gz') or prop_name.endswith('.mgz') or prop_name.endswith('.mgh.gz'):
            prop_mime = 'application/x-gzip'
        elif prop_name.endswith('.nii'):
            prop_mime = 'application/NIfTI-1'
        elif prop_name.endswith('.mgh'):
            prop_mime = 'application/MGH'
        else:
            raise ValueError('unsupported file type: ' + prop_name)
        # Create a new object identifier.
        identifier = str(uuid.uuid4()).replace('-','')
        # The object directory is given by the object identifier.
        object_dir = os.path.join(self.directory, identifier)
        # Create (sub-)directories for the uploaded and extracted data files.
        if not os.access(object_dir, os.F_OK):
            os.makedirs(object_dir)
        data_dir = os.path.join(object_dir, DATA_DIRECTORY)
        os.mkdir(data_dir)
        func_data_file = prop_name
        uploaded_file = os.path.join(data_dir, prop_name)
        shutil.copyfile(filename, uploaded_file)
        # Create the initial set of properties for the new image object.
        properties = {
            datastore.PROPERTY_NAME: prop_name,
            datastore.PROPERTY_FILENAME : prop_name,
            datastore.PROPERTY_FILESIZE : os.path.getsize(uploaded_file),
            datastore.PROPERTY_MIMETYPE : prop_mime,
            datastore.PROPERTY_FUNCDATAFILE : func_data_file
        }
        if read_only:
            properties[datastore.PROPERTY_READONLY] = True
        # Create object handle and store it in database before returning it
        obj = FunctionalDataHandle(
            identifier,
            properties,
            object_dir
        )
        self.insert_object(obj)
        return obj

    def from_dict(self, document):
        """Create functional data object from JSON document retrieved from
        database.

        Parameters
        ----------
        document : JSON
            Json document in database

        Returns
        -------
        FunctionalDataHandle
            Handle for functional data object
        """
        identifier = str(document['_id'])
        active = document['active']
        # The directory is not materilaized in database to allow moving the
        # base directory without having to update the database.
        directory = os.path.join(self.directory, identifier)
        timestamp = datetime.datetime.strptime(document['timestamp'], '%Y-%m-%dT%H:%M:%S.%f')
        properties = document['properties']
        return FunctionalDataHandle(identifier, properties, directory, timestamp=timestamp, is_active=active)
