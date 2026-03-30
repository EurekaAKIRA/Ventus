interface JsonViewerProps {
  data: unknown;
}

export default function JsonViewer({ data }: JsonViewerProps) {
  return (
    <pre className="json-viewer">{JSON.stringify(data, null, 2)}</pre>
  );
}
