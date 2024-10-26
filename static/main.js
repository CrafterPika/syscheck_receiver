function openReport() {
    let report_id = document.getElementById("report_id").value;
    window.open(`/view_report?id=${report_id}`, '_blank').focus();
};
document.getElementById("submit-btn").addEventListener("click", openReport);