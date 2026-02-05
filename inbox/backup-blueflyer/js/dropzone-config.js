Dropzone.autoDiscover = false;

document.addEventListener("DOMContentLoaded", function () {
  // Initialize Dropzone
  const dropzoneElement = document.getElementById("my-dropzone");

  if (!dropzoneElement) {
    console.error("Dropzone element not found");
    return;
  }

  const myDropzone = new Dropzone(dropzoneElement, {
    url: "/api/upload",
    autoProcessQueue: false,
    maxFiles: 4,
    acceptedFiles: "image/*",
    addRemoveLinks: false,
    createImageThumbnails: true,
    thumbnailWidth: 120,
    thumbnailHeight: 120,
    clickable: true,
    dictDefaultMessage:
      '<i class="fas fa-image" aria-hidden="true"></i><br>Drag and drop images here or click to upload<br><small>(max 4 images)</small>',
    previewTemplate: `
      <div class="dz-preview dz-file-preview image-preview-container">
        <div class="preview-controls">
          <div class="preview-sequence-number"></div>
          <div class="image-controls">
            <button type="button" class="image-control-btn try-again-btn" aria-label="Try generating alt text again" title="Regenerate description">
              <i class="fas fa-sync-alt"></i>
            </button>
            <button type="button" class="image-control-btn remove-btn" aria-label="Remove image" title="Remove image" data-dz-remove>
              <i class="fas fa-times"></i>
            </button>
          </div>
        </div>
        <div class="dz-image">
          <img data-dz-thumbnail class="preview-image" />
        </div>
        <div class="alt-text-area">
          <div class="alt-text-editor" contenteditable="true" role="textbox" aria-multiline="true" aria-label="Image description" placeholder="Image description (alt text)"></div>
        </div>
        <div class="dz-error-message"><span data-dz-errormessage></span></div>
      </div>
    `,
    init: function () {
      const dz = this;

      // Update sequence numbers when files change
      function updateSequenceNumbers() {
        const previews = dz.element.querySelectorAll(".dz-preview");
        previews.forEach((preview, index) => {
          const seqNum = preview.querySelector(".preview-sequence-number");
          if (seqNum) {
            seqNum.textContent = index + 1;
          }
        });
      }

      // Handle file addition
      this.on("addedfile", function (file) {
        console.log("File added:", file.name);
        updateSequenceNumbers();

        // Setup try again button handler
        const tryAgainBtn = file.previewElement.querySelector(".try-again-btn");
        if (tryAgainBtn) {
          tryAgainBtn.addEventListener("click", async function () {
            const loadingOverlay =
              file.previewElement.querySelector(".preview-loading");
            if (loadingOverlay) {
              loadingOverlay.style.display = "flex";
            }

            try {
              const altText = await window.altTextGenerator.generateAltText(
                file
              );
              const altTextEditor =
                file.previewElement.querySelector(".alt-text-editor");
              if (altTextEditor) {
                altTextEditor.textContent = altText;
              }
            } catch (error) {
              console.error("Error regenerating alt text:", error);
            } finally {
              if (loadingOverlay) {
                loadingOverlay.style.display = "none";
              }
            }
          });
        }

        // Generate initial alt text
        (async () => {
          const loadingOverlay =
            file.previewElement.querySelector(".preview-loading");
          try {
            const altText = await window.altTextGenerator.generateAltText(file);
            const altTextEditor =
              file.previewElement.querySelector(".alt-text-editor");
            if (altTextEditor) {
              altTextEditor.textContent = altText;
            }
          } catch (error) {
            console.error("Error generating initial alt text:", error);
          } finally {
            if (loadingOverlay) {
              loadingOverlay.style.display = "none";
            }
          }
        })();
      });

      // Handle file removal
      this.on("removedfile", function () {
        console.log("File removed");
        updateSequenceNumbers();
      });

      // Handle max files exceeded
      this.on("maxfilesexceeded", function (file) {
        console.log("Max files exceeded");
        dz.removeFile(file);
        alert("Maximum 4 images allowed");
      });

      // Handle file sending
      this.on("sending", function (file, xhr, formData) {
        const altTextEl = file.previewElement.querySelector(".alt-text-editor");
        if (altTextEl) {
          formData.append(
            "altText",
            altTextEl.textContent || altTextEl.value || ""
          );
        }
      });

      // Handle errors
      this.on("error", function (file, errorMessage) {
        console.error("Dropzone error:", errorMessage);
      });
    },
  });

  // Export dropzone instance for external access if needed
  window.myDropzone = myDropzone;
});
