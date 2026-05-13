export const ok = (res, data = null, message = "OK") =>
  res.status(200).json({ success: true, message, data });

export const created = (res, data = null, message = "Creado") =>
  res.status(201).json({ success: true, message, data });
