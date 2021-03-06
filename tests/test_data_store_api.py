import gzip
import os
import shutil
import sys
import unittest

import scodata.mongo as mongo
import scodata as api
import scodata.attribute as attributes
import scodata.datastore as datastore
import scodata.modelrun as prediction

from scodata.experiment import TYPE_EXPERIMENT
from scodata.funcdata import TYPE_FUNCDATA
from scodata.image import TYPE_IMAGE, TYPE_IMAGE_GROUP, TYPE_PREDICTION_IMAGE_SET
from scodata.modelrun import TYPE_MODEL_RUN
from scodata.subject import TYPE_SUBJECT


API_DIR = '/tmp/sco'
DATA_DIR = './data'
CSV_FILE = './data/csv/attachment1.csv'

class TestSCODataStoreAPIMethods(unittest.TestCase):

    def setUp(self):
        """Connect to MongoDB and clear any existing collections. Ensure
        that data directory exists and is empty. Then create API."""
        self.SUBJECT_FILE = os.path.join(DATA_DIR, 'subjects/ernie.tar.gz')
        self.IMAGE_FILE = os.path.join(DATA_DIR, 'images/collapse.gif')
        self.NON_IMAGE_FILE = os.path.join(DATA_DIR, 'images/no-image.txt')
        self.IMAGE_GROUP_FILE = os.path.join(DATA_DIR, 'images/images.tar.gz')
        self.PRED_IMAGE_SET_FILE = os.path.join(DATA_DIR, 'images/images.tar.gz')
        self.FMRI_FILE = os.path.join(DATA_DIR, 'fmris/data.mgz')
        m = mongo.MongoDBFactory(db_name='scotest')
        db = m.get_database()
        db.experiments.drop()
        db.funcdata.drop()
        db.images.drop()
        db.imagegroups.drop()
        db.predictions.drop()
        db.subjects.drop()
        if os.path.isdir(API_DIR):
            shutil.rmtree(API_DIR)
        os.makedirs(API_DIR)
        self.api = api.SCODataStore(m, API_DIR)

    def test_experiment_api(self):
        # Create subject and image group
        subject = self.api.subjects_create(self.SUBJECT_FILE)
        img_grp = self.api.images_create(self.IMAGE_GROUP_FILE)
        #
        # Create experiment
        #
        experiment = self.api.experiments_create(subject.identifier, img_grp.identifier, {'name':'Name'})
        # Ensure it is of expected type
        self.assertEquals(experiment.type, TYPE_EXPERIMENT)
        # Ensure that creating experiment with missing subject or image group
        # raises an Exception
        with self.assertRaises(ValueError):
            self.api.experiments_create('not-a-valid-idneitifer', img_grp.identifier, {'name':'Name'})
        with self.assertRaises(ValueError):
            self.api.experiments_create(subject.identifier, 'not-a-valid-idneitifer', {'name':'Name'})
        #
        # Get
        #
        experiment = self.api.experiments_get(experiment.identifier)
        # Ensure it is of expected type
        self.assertEquals(experiment.type, TYPE_EXPERIMENT)
        # Ensure that get experiment with invalid identifier is None
        self.assertIsNone(self.api.experiments_get('not-a-valid-identifier'))
        #
        # fMRI
        #
        self.assertIsNone(self.api.experiments_fmri_get(experiment.identifier))
        #
        # List
        #
        self.assertEqual(self.api.experiments_list().total_count, 1)
        #
        # Upsert property
        #
        experiment = self.api.experiments_upsert_property(
            experiment.identifier,
            {datastore.PROPERTY_NAME : 'Some Name',
            'someprop' : 'somevalue'}
        )
        self.assertIsNotNone(experiment)
        # Ensure that properties are set as expected
        experiment = self.api.experiments_get(experiment.identifier)
        self.assertEqual(experiment.properties[datastore.PROPERTY_NAME], 'Some Name')
        self.assertEqual(experiment.properties['someprop'], 'somevalue')
        # Ensure that existing properities are not affected if not in upsert
        experiment = self.api.experiments_upsert_property(
            experiment.identifier,
            {datastore.PROPERTY_NAME : 'Some Other Name'}
        )
        self.assertIsNotNone(experiment)
        # Ensure that properties are set as expected
        experiment = self.api.experiments_get(experiment.identifier)
        self.assertEqual(experiment.properties[datastore.PROPERTY_NAME], 'Some Other Name')
        self.assertTrue('someprop' in experiment.properties)
        # Delete Property
        experiment = self.api.experiments_upsert_property(
            experiment.identifier,
            {datastore.PROPERTY_NAME : 'Some Other Name',
            'someprop':None}
        )
        self.assertIsNotNone(experiment)
        # Ensure that properties are set as expected
        experiment = self.api.experiments_get(experiment.identifier)
        self.assertEqual(experiment.properties[datastore.PROPERTY_NAME], 'Some Other Name')
        self.assertFalse('someprop' in experiment.properties)
        #
        # Delete
        #
        self.assertIsNotNone(self.api.experiments_delete(experiment.identifier))
        # Ensure that the list of experiments contains no elements
        self.assertEqual(self.api.experiments_list().total_count, 0)
        # Ensure that deleting a deleted experiment returns None
        self.assertIsNone(self.api.experiments_delete(experiment.identifier))
        # Updating the name of deleted experiment should return None
        self.assertIsNone(
            self.api.experiments_upsert_property(
                experiment.identifier,
                {datastore.PROPERTY_NAME : 'Some Name'}
            )
        )

    def test_experiment_fmri_api(self):
        # Create subject and image group and experiment
        subject = self.api.subjects_create(self.SUBJECT_FILE)
        img_grp = self.api.images_create(self.IMAGE_GROUP_FILE)
        experiment = self.api.experiments_create(subject.identifier, img_grp.identifier, {'name':'Name'})
        #
        # Create experiment fMRI object
        #
        fmri = self.api.experiments_fmri_create(experiment.identifier, self.FMRI_FILE)
        # Ensure that object is of expected type
        self.assertEquals(fmri.type, TYPE_FUNCDATA)
        # Ensure that creating fMRI for unknown experiment returns None
        self.assertIsNone(self.api.experiments_fmri_create('not-a-valid-identifier', self.FMRI_FILE))
        #
        # Get
        #
        fmri = self.api.experiments_fmri_get(experiment.identifier)
        # Ensure that object is of expected type
        self.assertEquals(fmri.type, TYPE_FUNCDATA)
        #
        # Download
        #
        self.assertTrue(os.path.isfile(self.api.experiments_fmri_download(experiment.identifier).file))
        #
        # Upsert property
        #
        self.assertIsNotNone(
            self.api.experiments_fmri_upsert_property(
                experiment.identifier,
                {datastore.PROPERTY_NAME : 'Some Name'}
            )
        )
        #
        # Delete
        #
        self.assertIsNotNone(self.api.experiments_fmri_delete(experiment.identifier))
        # Ensure that the fMRI for experiment is None
        self.assertIsNone(self.api.experiments_fmri_get(experiment.identifier))
        # Ensure that deleting a deleted experiment returns None
        self.assertIsNone(self.api.experiments_fmri_delete(experiment.identifier))
        # Updating the name of deleted experiment should return None
        self.assertIsNone(
            self.api.experiments_fmri_upsert_property(
                experiment.identifier,
                {datastore.PROPERTY_NAME : 'Some Name'}
            )
        )
        # File info should be None
        self.assertIsNone(self.api.experiments_fmri_download(experiment.identifier))


    def test_experiment_prediction_api(self):
        # Create subject and image group and experiment
        subject = self.api.subjects_create(self.SUBJECT_FILE)
        img_grp = self.api.images_create(self.IMAGE_GROUP_FILE)
        experiment = self.api.experiments_create(subject.identifier, img_grp.identifier, {'name':'Name'})
        #
        # Create experiment prediction object
        #
        model_run = self.api.experiments_predictions_create(experiment.identifier, 'Model', [], 'Name')
        # Ensure that object is of expected type
        self.assertEquals(model_run.type, TYPE_MODEL_RUN)
        # Ensure that creating fMRI for unknown experiment returns None
        self.assertIsNone(self.api.experiments_predictions_create('not-a-valid-identifier', 'Model', [], 'Name'))
        # Create second experiment and prediction with arguments
        exp2 = self.api.experiments_create(subject.identifier, img_grp.identifier, {'name':'Name'})
        attrDefs = [
            attributes.AttributeDefinition(
                'gabor_orientations',
                'gabor_orientations',
                '',
                attributes.FloatType()
            ),
            attributes.AttributeDefinition(
                'max_eccentricity',
                'max_eccentricity',
                '',
                attributes.IntType()
            )
        ]
        mr2 = self.api.experiments_predictions_create(
            exp2.identifier,
            'Model',
            attrDefs,
            'Name',
            arguments=[
                {'name': 'gabor_orientations', 'value': 10},
                {'name': 'max_eccentricity', 'value': 11}
            ]
        )
        #
        # Get
        #
        model_run = self.api.experiments_predictions_get(experiment.identifier, model_run.identifier)
        # Ensure object is of expected type
        self.assertEquals(model_run.type, TYPE_MODEL_RUN)
        # Ensure invalud experiment and prediction combination is None
        self.assertIsNone(self.api.experiments_predictions_get(experiment.identifier, mr2.identifier))
        self.assertIsNone(self.api.experiments_predictions_get(exp2.identifier, model_run.identifier))
        self.assertIsNone(self.api.experiments_predictions_get('not-a-valid-identifier', mr2.identifier))
        self.assertIsNone(self.api.experiments_predictions_get(experiment.identifier, 'not-a-valid-identifier'))
        #
        # Download
        #
        self.assertIsNone(self.api.experiments_predictions_download(experiment.identifier, model_run.identifier))
        #
        # List
        #
        self.assertEqual(self.api.experiments_predictions_list(experiment.identifier).total_count, 1)
        #
        # Upsert properties
        #
        self.assertIsNotNone(
            self.api.experiments_predictions_upsert_property(
                experiment.identifier,
                model_run.identifier,
                {datastore.PROPERTY_NAME : 'Some Name'}
            )
        )
        #
        # State
        #
        self.assertTrue(model_run.state.is_idle)
        model_run = self.api.experiments_predictions_update_state_active(
            experiment.identifier,
            model_run.identifier
        )
        # Ensure that state change has happened and is persistent
        self.assertTrue(model_run.state.is_running)
        # Set state to success
        model_run = self.api.experiments_predictions_update_state_success(
            experiment.identifier,
            model_run.identifier,
            self.FMRI_FILE
        )
        model_run = self.api.experiments_predictions_get(experiment.identifier, model_run.identifier)
        self.assertTrue(model_run.state.is_success)
        # Attach file to successful model run
        self.api.experiments_predictions_attachments_create(
            experiment.identifier,
            model_run.identifier,
            'attachment',
            CSV_FILE
        )
        # Read attached file. Content should be '1'
        file_info = self.api.experiments_predictions_attachments_download(
            experiment.identifier,
            model_run.identifier,
            'attachment',
        )
        with open(file_info.file, 'r') as f:
            self.assertEquals(f.read().strip(), '1')
        # Delete attached file
        self.assertTrue(self.api.experiments_predictions_attachments_delete(
            experiment.identifier,
            model_run.identifier,
            'attachment',
        ))
        # Creating a model run with unknown parameter should raise ValueError
        with self.assertRaises(ValueError):
            self.api.experiments_predictions_create(
                exp2.identifier,
                'Model',
                attrDefs,
                'Name',
                arguments=[
                    {'name': 'gabor_orientations', 'value': 10},
                    {'name': 'contrast_constants_by_label', 'value': 11}
                ]
            )
        # Creating a model run with invalid parameter value should raise ValueError
        with self.assertRaises(ValueError):
            self.api.experiments_predictions_create(
                exp2.identifier,
                'Model',
                attrDefs,
                'Name',
                arguments=[
                    {'name': 'gabor_orientations', 'value': 'ten'}
                ]
            )

    def test_image_files_api(self):
        """Test all image file related methods of API."""
        #
        # Create image object file
        #
        img = self.api.images_create(self.IMAGE_FILE)
        # Ensure that the created object is an image file
        self.assertEquals(img.type, TYPE_IMAGE)
        # Ensure that creating image with invalid suffix raises Exception
        with self.assertRaises(ValueError):
            self.api.images_create(self.NON_IMAGE_FILE)
        #
        # Get image and ensure that it is still of expected type
        #
        img = self.api.image_files_get(img.identifier)
        self.assertEquals(img.type, TYPE_IMAGE)
        # Ensure that getting an image with unknown identifier is None
        self.assertIsNone(self.api.image_files_get('not-a-valid-identifier'))
        #
        # Ensure that the list of images contains one element
        #
        self.assertEqual(self.api.image_files_list().total_count, 1)
        #
        # Ensure that the download file exists
        #
        self.assertTrue(os.path.isfile(self.api.image_files_download(img.identifier).file))
        # The download for a non-existing image should be None
        self.assertIsNone(self.api.image_files_download('not-a-valid-identifier'))
        #
        # Updating the image name should return object handle
        #
        self.assertIsNotNone(
            self.api.image_files_upsert_property(
                img.identifier,
                {datastore.PROPERTY_NAME : 'Some Name'}
            )
        )
        # Updating the file name should raise exception
        with self.assertRaises(ValueError):
            self.api.image_files_upsert_property(
                img.identifier,
                {datastore.PROPERTY_FILENAME : 'Some.Name'}
            )
        #
        # Assert that delete returns not None
        #
        self.assertIsNotNone(self.api.image_files_delete(img.identifier))
        # Ensure that the list of images contains no elements
        self.assertEqual(self.api.image_files_list().total_count, 0)
        # Ensure that deleting a deleted image returns None
        self.assertIsNone(self.api.image_files_delete(img.identifier))
        # Updating the name of deleted image should return None
        self.assertIsNone(
            self.api.image_files_upsert_property(
                img.identifier,
                {datastore.PROPERTY_NAME : 'Some Name'}
            )
        )

    def test_image_groups_api(self):
        """Test all image group related methods of API."""
        # Create image group object from file
        img_grp = self.api.images_create(self.IMAGE_GROUP_FILE)
        # Ensure that the created object is an image group
        self.assertEquals(img_grp.type, TYPE_IMAGE_GROUP)
        # Get image group and ensure that it is still of expected type
        img_grp = self.api.image_groups_get(img_grp.identifier)
        self.assertEquals(img_grp.type, TYPE_IMAGE_GROUP)
        # Ensure that getting an image group with unknown identifier is None
        self.assertIsNone(self.api.image_groups_get('not-a-valid-identifier'))
        # Ensure that the list of image groups contains one element
        self.assertEqual(self.api.image_groups_list().total_count, 1)
        # Ensure that the download file exists
        self.assertTrue(os.path.isfile(self.api.image_groups_download(img_grp.identifier).file))
        # The download for a non-existing image should be None
        self.assertIsNone(self.api.image_groups_download('not-a-valid-identifier'))
        # Updating the image group name should return object handle
        self.assertIsNotNone(
            self.api.image_groups_upsert_property(
                img_grp.identifier,
                {datastore.PROPERTY_NAME : 'Some Name'}
            )
        )
        # Updating the file name should raise exception
        with self.assertRaises(ValueError):
            self.api.image_groups_upsert_property(
                img_grp.identifier,
                {datastore.PROPERTY_FILENAME : 'Some.Name'}
            )
        # Ensure that updating options does not raise exception
        self.assertIsNotNone(self.api.image_groups_update_options(
            img_grp.identifier,
            [
                attributes.Attribute('pixels_per_degree', 0.8),
                attributes.Attribute('aperture_edge_width', 0.75)
            ]
        ))
        # Ensure that exception is raised if unknown attribute name is given
        with self.assertRaises(ValueError):
            self.api.image_groups_update_options(
                img_grp.identifier,
                [
                    attributes.Attribute('not_a_defined_attribute', 0.8),
                    attributes.Attribute('pixels_per_degree', 0.75)
                ]
            )
        self.assertIsNotNone(self.api.image_groups_delete(img_grp.identifier))
        # Ensure that the list of image groups contains no elements
        self.assertEqual(self.api.image_groups_list().total_count, 0)
        # Ensure that deleting a deleted image group returns None
        self.assertIsNone(self.api.image_groups_delete(img_grp.identifier))
        # Updating the name of deleted image should return None
        self.assertIsNone(
            self.api.image_groups_upsert_property(
                img_grp.identifier,
                {datastore.PROPERTY_NAME : 'Some Name'}
            )
        )

    def test_prediction_image_sets_api(self):
        """Test all prediction image set related methods of API."""
        # Create subject and image group and experiment
        subject = self.api.subjects_create(self.SUBJECT_FILE)
        img_grp = self.api.images_create(self.IMAGE_GROUP_FILE)
        experiment = self.api.experiments_create(subject.identifier, img_grp.identifier, {'name':'Name'})
        model_run = self.api.experiments_predictions_create(experiment.identifier, 'Model', [], 'Name')
        model_run = self.api.experiments_predictions_update_state_active(
            experiment.identifier,
            model_run.identifier
        )
        # Ensure that creating a prediction image set for unfinished run Raises
        # an exception
        with self.assertRaises(ValueError):
            img_sets = self.api.experiments_predictions_image_set_create(
                experiment.identifier,
                model_run.identifier,
                self.PRED_IMAGE_SET_FILE
            )
        # Set state to success
        model_run = self.api.experiments_predictions_update_state_success(
            experiment.identifier,
            model_run.identifier,
            self.FMRI_FILE
        )
        # Create prediction image set collection from file
        img_sets = self.api.experiments_predictions_image_set_create(
            experiment.identifier,
            model_run.identifier,
            self.PRED_IMAGE_SET_FILE
        )
        # Ensure that the created object is an prediction image set handle
        self.assertEquals(img_sets.type, TYPE_PREDICTION_IMAGE_SET)

    def test_subjects_api(self):
        """Test all subject related methods of API."""
        # Create temp subject file
        subject = self.api.subjects_create(self.SUBJECT_FILE)
        # Ensure that the created object is a subject
        self.assertEquals(subject.type, TYPE_SUBJECT)
        # Get subject and ensure that it is still a subject
        subject = self.api.subjects_get(subject.identifier)
        self.assertEquals(subject.type, TYPE_SUBJECT)
        # Ensure that getting a subject with unknown identifier is None
        self.assertIsNone(self.api.subjects_get('not-a-valid-identifier'))
        # Ensure that the list of subjects contains one element
        self.assertEqual(self.api.subjects_list().total_count, 1)
        # Ensure that the download file exists
        self.assertTrue(os.path.isfile(self.api.subjects_download(subject.identifier).file))
        # The download for a non-existing subject should be None
        self.assertIsNone(self.api.subjects_download('not-a-valid-identifier'))
        # Updating the subject name should return object handle
        self.assertIsNotNone(
            self.api.subjects_upsert_property(
                subject.identifier,
                {datastore.PROPERTY_NAME : 'Some Name'}
            )
        )
        # Updating the file name should raise exception
        with self.assertRaises(ValueError):
            self.api.subjects_upsert_property(
                subject.identifier,
                {datastore.PROPERTY_FILENAME : 'Some.Name'}
            )
        # Assert that delete returns not None
        self.assertIsNotNone(self.api.subjects_delete(subject.identifier))
        # Ensure that the list of subjects contains no elements
        self.assertEqual(self.api.subjects_list().total_count, 0)
        # Ensure that deleting a deleted subject returns None
        self.assertIsNone(self.api.subjects_delete(subject.identifier))
        # Updating the name of deleted subject should return None
        self.assertIsNone(
            self.api.subjects_upsert_property(
                subject.identifier,
                {datastore.PROPERTY_NAME : 'Some Name'}
            )
        )

if __name__ == '__main__':
    # Pass data directory as optional parameter
    if len(sys.argv) == 2:
        DATA_DIR = sys.argv[1]
    sys.argv = sys.argv[:1]
    unittest.main()
