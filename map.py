import matplotlib.pyplot as plt
import matplotlib.colors
import geoip2.database
from sklearn.cluster import DBSCAN
import matplotlib.gridspec as gridspec
from cartopy.io.img_tiles import *
from math import log
import fire


def cluster_coordinates(coordinates, eps=1.5, min_samples=1):
    """
    Use DBSCAN to cluster points and have a readable map
    :param coordinates: list of points (lat, lon)
    :param eps: control the density of the cluster
    :param min_samples: minimum number of samples in a cluster
    """
    dbscan = DBSCAN(eps=eps, min_samples=min_samples)
    dbscan.fit(coordinates)
    labels = dbscan.labels_
    cluster_centers = []
    cluster_counts = []
    unique_labels = set(labels)
    for label in unique_labels:
        if label == -1:
            continue
        cluster_mask = (labels == label)
        cluster_points = coordinates[cluster_mask]
        cluster_centers.append(np.mean(cluster_points, axis=0))
        cluster_counts.append(np.sum(cluster_mask))

    cluster_points = coordinates[(labels == -1)]
    cluster_centers += list(cluster_points)
    cluster_counts += [1] * len(cluster_points)
    r = list(zip(cluster_centers, cluster_counts))
    return r, max(cluster_counts), min(cluster_counts)


def geo_ip(ip, reader):
    """
    Geocode IP address using the given reader
    :param ip: IP address
    :param reader: a geoip2.database.Reader
    :return: [lon, lat] location
    """
    response = reader.city(ip)
    return [response.location.longitude, response.location.latitude]


def get_ip_from_consensus(filename):
    """
    Get the IP addresses of the relays present in the consensus at filename
    :param filename: filename of the consensus
    :return: list of IP of the relays in the consensus
    """
    result = []
    with open(filename, 'r') as file:
        for line in file:
            if line.startswith("r "):
                fields = line.split()
                if len(fields) >= 7:
                    result.append(fields[6])
    return result


def main(consensus_file, geoip_data_file, eps=1.5):
    """
    Create a map based on the consensus_file and geoip_data_file
    :param consensus_file: filename of a Tor consensus, see https://metrics.torproject.org/collector/recent/relay-descriptors/consensuses/
    :param geoip_data_file: MaxMind mmdb filename, see https://dev.maxmind.com/geoip/geolite2-free-geolocation-data
    :param eps: control the density of the cluster on the map
    """
    print('Reading consensus file')
    ips = get_ip_from_consensus(consensus_file)
    print(f'Found {len(ips)} relays')
    points = list()
    print('Geocoding IP addresses')
    reader = geoip2.database.Reader(geoip_data_file)
    for ip in ips:
        points.append(geo_ip(ip, reader))
    points = np.array(points)
    points, vmax, vmin = cluster_coordinates(points, eps=eps)

    fig = plt.figure(figsize=(10, 5))
    gs = gridspec.GridSpec(2, 1, height_ratios=[1, 0.05], figure=fig)
    ax = fig.add_subplot(gs[0], projection=ccrs.PlateCarree())

    ax.stock_img()
    ax.coastlines()

    # TODO if you want to use OSM data with Mapbox, create an account and a custom style on Mapbox.
    #  Then, fill the credentials below, comment the ax.stock_img() and ax.coastlines() lines and
    #  uncomment the lines below
    #  see https://docs.mapbox.com/help/tutorials/create-a-custom-style/
    # osm_tiles = MapboxStyleTiles(
    #     access_token='',
    #     map_id='',
    #     username='',
    #     cache=False)
    # ax.add_image(osm_tiles, 4)

    cmap = plt.cm.hot
    norm = matplotlib.colors.LogNorm(vmin=vmin, vmax=vmax)
    for pos, count in points:
        ax.plot(pos[0], pos[1], 'o', markersize=max(4 * log(count, 10), 2), transform=ccrs.PlateCarree(),
                color=cmap(norm(count)))

    ax.set_global()
    plt.box(False)
    ax.set_extent([-170, 180, -60, 85], crs=ccrs.PlateCarree())
    cb_ax = fig.add_subplot(gs[1])

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    cbar = plt.colorbar(sm, cax=cb_ax, orientation='horizontal')
    cbar.set_label('Number of relays')

    plt.tight_layout()
    print('Saving map as map.png')
    plt.savefig('map.png', dpi=300)


if __name__ == '__main__':
    fire.Fire(main)
