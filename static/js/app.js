const form = document.getElementById("predictForm");
const imageInput = document.getElementById("imageInput");
const fileLabel = document.getElementById("fileLabel");
const statusBox = document.getElementById("status");
const resultImage = document.getElementById("resultImage");
const emptyState = document.getElementById("emptyState");
const rows = document.getElementById("resultRows");
const submitBtn = document.getElementById("submitBtn");

imageInput.addEventListener("change", () => {
  const file = imageInput.files[0];
  fileLabel.textContent = file ? file.name : "انتخاب تصویر رادیوگرافی";
});

function fmt(value) {
  return value === null || value === undefined || Number.isNaN(value) ? "-" : Number(value).toFixed(3);
}

function setStatus(text, isError = false) {
  statusBox.textContent = text;
  statusBox.classList.toggle("error", isError);
}

function renderRows(predictions) {
  rows.innerHTML = "";
  if (!predictions.length) {
    rows.innerHTML = '<tr><td colspan="5">دندانی تشخیص داده نشد.</td></tr>';
    return;
  }

  for (const item of predictions) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${item.tooth_type}</td>
      <td>${fmt(item.pred_length_mm)}</td>
      <td>${fmt(item.pred_length_yolo_mm)}</td>
      <td>${fmt(item.pred_length_alt_mm)}</td>
      <td>${fmt(item.det_conf)}</td>
    `;
    rows.appendChild(tr);
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!imageInput.files.length) {
    setStatus("ابتدا یک تصویر انتخاب کن.", true);
    return;
  }

  submitBtn.disabled = true;
  setStatus("مدل در حال اجراست...");

  try {
    const response = await fetch("/predict", {
      method: "POST",
      body: new FormData(form),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "خطا در اجرای مدل");
    }

    resultImage.src = `${data.overlay_url}?t=${Date.now()}`;
    resultImage.style.display = "block";
    emptyState.style.display = "none";
    renderRows(data.predictions);
    const warningText = data.warnings && data.warnings.length ? ` | ${data.warnings.join(" | ")}` : "";
    setStatus(`اجرا کامل شد. روش: ${data.method}${warningText}`);
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    submitBtn.disabled = false;
  }
});
