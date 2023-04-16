from werkzeug.utils import secure_filename
from azure.storage.blob import BlobServiceClient
import os

def upload_image(image, blob_service):
    filename = secure_filename(image.filename)
    image.save(filename)

    blob_client = blob_service.get_blob_client(container="images", blob=filename)
    with open(filename, "rb") as data:
        try:
            blob_client.upload_blob(data, overwrite=True)
            msg = "Upload Successful"
        except:
            pass
    os.remove(filename)
