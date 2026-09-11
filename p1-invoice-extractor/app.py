import streamlit as st
import tempfile
import json
from reader import file_to_images
from extractor import extract

st.title("Invoice Field Extractor")
st.caption("Upload an invoice - get clean JSON back. Missing fields return null, never a guess.")

uploaded = st.file_uploader(
    label="Upload an invoice (PDF, JPG, PNG)",
    type=["pdf", "jpg", "jpeg", "png"],
)

if uploaded:
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded.name.split('.')[-1]}") as tmp:
        tmp.write(uploaded.read())
        tmp_path = tmp.name

    with st.spinner("Extracting fields..."):
        try:
            images = file_to_images(tmp_path)
            result = extract(images)
        except Exception as e:
            st.error(f"Error occurred while extracting invoice fields: {e}")
            st.stop()

    st.success("Extraction complete!")

    st.subheader("Extracted Fields")
    display = result.model_dump(mode="json")
    st.dataframe(
        data={"Field": list(display.keys()),
              "Value": [str(v) if v is not None else "—" for v in display.values()]},
        width="stretch",
    )

    st.download_button(
        label="Download JSON",
        data=result.model_dump_json(indent=2),
        file_name=f"{uploaded.name}.json",
        mime="application/json",
    )
