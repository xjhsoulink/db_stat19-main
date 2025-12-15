try:
    import geopandas as gpd
    from shapely.geometry import Point
    HAS_GEOPANDAS = True
except ImportError:
    HAS_GEOPANDAS = False
    Point = None
    print("Warning: geopandas not installed. Spatial conversion will be skipped.")

def format_sf(df):
    """
    Converts DataFrame to GeoDataFrame if coordinates exist.
    """
    if not HAS_GEOPANDAS:
        return df
        
    # Check for coordinates
    # Usually longitude/latitude or location_easting_osgr/location_northing_osgr
    
    # Prefer Longitude/Latitude (WGS84)
    if 'longitude' in df.columns and 'latitude' in df.columns:
        print("Converting to GeoDataFrame using Longitude/Latitude...")
        # Drop rows with NaN coordinates
        df_geo = df.dropna(subset=['longitude', 'latitude']).copy()
        geometry = [Point(xy) for xy in zip(df_geo.longitude, df_geo.latitude)]
        gdf = gpd.GeoDataFrame(df_geo, geometry=geometry, crs="EPSG:4326")
        return gdf
        
    # Fallback to OSGR (British National Grid)
    elif 'location_easting_osgr' in df.columns and 'location_northing_osgr' in df.columns:
        print("Converting to GeoDataFrame using OSGR...")
        df_geo = df.dropna(subset=['location_easting_osgr', 'location_northing_osgr']).copy()
        geometry = [Point(xy) for xy in zip(df_geo.location_easting_osgr, df_geo.location_northing_osgr)]
        gdf = gpd.GeoDataFrame(df_geo, geometry=geometry, crs="EPSG:27700")
        # Convert to WGS84 for general use
        gdf = gdf.to_crs("EPSG:4326")
        return gdf
        
    else:
        print("No coordinate columns found for spatial conversion.")
        return df
